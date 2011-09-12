# This Python file uses the following encoding: utf-8
import urllib
import os
from google.appengine.api.mail import EmailMessage
from google.appengine.ext.db import is_in_transaction
from google.appengine.api import taskqueue
from google.appengine.api.images import BadImageError, NotImageError
from django.utils.translation import ugettext as _
from django.shortcuts import render_to_response
from django.db.models.fields import related
from django.db import models
from django.core.validators import RegexValidator
from django.conf import settings
from common.errors import TransactionError
from settings import NO_REPLY_SENDER
import hashlib
import datetime
import logging
import random
import re

MINUTE_DELTA = 60
HOUR_DELTA = MINUTE_DELTA * 60
DAY_DELTA = HOUR_DELTA * 24
MONTH_DELTA = DAY_DELTA * 30
YEAR_DELTA = DAY_DELTA * 365

class Enum(object):
    @classmethod
    def _item_names(cls):
        result = []
        for item_name in dir(cls):
            item = getattr(cls, item_name)
            if (isinstance(item, int) or isinstance(item, str)) and not item_name.startswith("_"):
                result.append(item_name)

        return result

    @classmethod
    def _items(cls):
        result = []
        for item_name in cls._item_names():
            result.append(getattr(cls, item_name))

        return result

    @classmethod
    def contains(cls, value):
        return value in cls._items()

    @classmethod
    def choices(cls):
        result = []
        for item_name in cls._item_names():
            item = getattr(cls, item_name)
            result.append((item, _(item_name.capitalize())))

        return sorted(result)

    @classmethod
    def get_name(cls, value):
        return cls._item_names()[cls._items().index(value)]

class Polygon(object):
    def __init__(self, points):
        self.polygon = list(split_to_tuples(points, 2))

    def __repr__(self):
        return unicode(self.polygon)
    
    def contains(self, lat, lon):
        return point_inside_polygon(lat, lon, self.polygon)

class EventType(Enum):
    ORDER_BOOKED = 1
    ORDER_ASSIGNED = 2
    ORDER_ACCEPTED = 3
    ORDER_REJECTED = 4
    ORDER_IGNORED = 5
    ORDER_ERROR = 6
    CROSS_COUNTRY_ORDER_FAILURE = 7
    NO_SERVICE_IN_CITY = 8
    NO_SERVICE_IN_COUNTRY = 9
    ORDER_FAILED = 10
    ORDER_RATED = 11
    UNREGISTERED_ORDER = 12
    PASSENGER_REGISTERED = 13
    ORDER_NOT_TAKEN = 14
    BUSINESS_REGISTERED = 15
    WORKSTATION_UP = 16
    WORKSTATION_DOWN = 17

    @classmethod
    def get_label(cls, val):
        for item_name in dir(cls):
            item_value = getattr(cls, item_name)
            if item_value == val:
                name = " ".join([p.capitalize() for p in item_name.split("_")])
                return _(name)

        raise ValueError(_("Invalid value: %s" % str(val)))

    @classmethod
    def get_icon(cls, val):
        for item_name in dir(cls):
            item_value = getattr(cls, item_name)
            if item_value == val:
                return "/static/images/%s_marker.png" % item_name.lower()

        raise ValueError(_("Invalid value: %s" % str(val)))

class TransactionalField(models.Field):
    def pre_save(self, model_instance, add):
        # Prevent changes outside of a transaction
        if model_instance.id:
            old_value = getattr(self.model.objects.get(id=model_instance.id), self.attname)
            new_value = getattr(model_instance, self.attname)
            if old_value != new_value:
                if not is_in_transaction():
                    raise TransactionError("%s updates must use transactions (old_val: %d, new_val: %d)" % (self.attname,old_value, new_value))

        return super(TransactionalField, self).pre_save(model_instance, add)

class StatusField(TransactionalField, models.IntegerField):
    pass

def is_empty(str):
    """
    return True pf string is empty, spaces only or None
    """
    return not str or len(str.strip()) == 0

def datetimeIterator(from_datetime=None, to_datetime=None, delta=datetime.timedelta(days=1)):
    """
    Return a generator iterating the dates between two datetime instances.
    """
    from_datetime = from_datetime or datetime.datetime.now()
    while to_datetime is None or from_datetime <= to_datetime:
        yield from_datetime
        from_datetime = from_datetime + delta
    return

# python weekdays (see: datetime.weekday()): monday=0 .. sunday=6
FIRST_WEEKDAY = 1
LAST_WEEKDAY = 7
PYTHON_WEEKDAY_MAP = {
    6: 1,
    0: 2,
    1: 3,
    2: 4,
    3: 5,
    4: 6,
    5: 7
}
DAY_OF_WEEK_CHOICES = ((1, _("Sunday")),
                       (2, _("Monday")),
                       (3, _("Tuesday")),
                       (4, _("Wednesday")),
                       (5, _("Thursday")),
                       (6, _("Friday")),
                       (7, _("Saturday")))

def convert_python_weekday(wd):
    return PYTHON_WEEKDAY_MAP[wd]


def gen_verification_code():
    return random.randrange(1000, 10000)

#    return 1234

def get_model_from_request(model_class, request):
    if not request.user or not request.user.is_authenticated():
        return None
    try:
        model_instance = model_class.objects.filter(user=request.user).get()
    except model_class.DoesNotExist:
        return None

    return model_instance


def get_current_version():
    return os.environ.get('CURRENT_VERSION_ID', '0')


def get_channel_key(model, key_data=""):
    cls = type(model)
    s = hashlib.sha1()
    if not key_data:
        key_data = generate_random_token()
    s.update(u"channel_key_%s_%d_%s" % (cls.__name__.lower(), model.id, key_data))
    return s.hexdigest()


def log_event(event_type, order=None, order_assignment=None, station=None, work_station=None, passenger=None,
              country=None, city=None, rating="", lat="", lon=""):
    """
    Log a new analytics event asynchronously:
        event_type: an EventType field (e.g. EventType.ORDER_BOOKED)
        order, order_assignment, station, work_station, passenger: an optional instance
    """
    if order: # fill values from order
        if not city:
            city = order.from_city
            country = order.from_country
            if order.from_city != order.to_city and order.to_city:
                log_event(event_type,
                          order=order, order_assignment=order_assignment, station=station, work_station=work_station,
                          passenger=passenger, country=order.from_country, city=order.to_city)

        if not lat: lat = order.from_lat
        if not lon: lon = order.from_lon

    params = {
        'event_type': event_type,
        'order_id': order.id if order else "",
        'order_assignment_id': order_assignment.id if order_assignment else "",
        'station_id': station.id if station else "",
        'work_station_id': work_station.id if work_station else "",
        'passenger_id': passenger.id if passenger else "",
        'country_id': country.id if country else "",
        'city_id': city.id if city else "",
        'rating': rating,
        'lat': lat,
        'lon': lon,
        }

    # Note that reverse was not used here to avoid circular import!
    task = taskqueue.Task(url="/services/log_event/", params=params)
    q = taskqueue.Queue('log-events')
    q.add(task)


def get_international_phone(country, local_phone):
    if local_phone.startswith("0"):
        local_phone = local_phone[1:]

    return "%s%s" % (country.dial_code, local_phone)


def custom_render_to_response(template, dictionary=None, context_instance=None, mimetype=None):
    """
    a wrapper around render_to_reponse

    if request.mobile = True then change template name to 'mobile/' + template
    """
    if not context_instance:
        raise RuntimeError("context_instance must be passed")

    for d in context_instance.dicts:
        if "mobile" in d and d["mobile"]:
            template = "%s/%s" % ('mobile', template)
            break

    return render_to_response(template, dictionary=dictionary, context_instance=context_instance, mimetype=mimetype)


def url_with_querystring(path, **kwargs):
    return path + '?' + urllib.urlencode(kwargs)


def generate_random_token(length=random.randint(10, 20), alpha_only=False, alpha_or_digit_only=False):
    s = ""
    while len(s) <= length:
        j = random.randint(33, 126)
        c = str(chr(j))
        if alpha_or_digit_only and (c.isalpha() or c.isdigit()):
            s += c
        elif alpha_only and c.isalpha():
            s += c
        elif not (alpha_only or alpha_or_digit_only):
            s += c
    return s


def get_unique_id():
    s = hashlib.sha1()
    s.update(str(datetime.datetime.now()) + generate_random_token(length=3))
    return s.hexdigest()


def notify_by_email(subject, msg=None, html=None):
    send_mail_as_noreply("notify@waybetter.com", "WAYbetter notification: %s" % subject, msg=msg, html=html)

def send_mail_as_noreply(address, subject, msg=None, html=None):
    logging.info(u"Sending email to %s: [%s] %s" % (address, subject, msg))
    try:
        mail = EmailMessage()
        mail.sender = NO_REPLY_SENDER
        mail.to = address
        mail.subject = subject
        if html:
            mail.html = html
        elif msg:
            mail.body = msg
        else:
            mail.body = "---" # mail.body cannot be empty string, raises exception

        mail.check_initialized()
        mail.send()
    except Exception, e:
        logging.error("Email sending failed: %s" % e.message)


def blob_to_image_tag(blob_data, height=50, width=None):
    """
    Convert blob image data to a uri encoded image tag.
    Perform size transforms if given height or width
    """
    import base64
    from google.appengine.api import images

    res = ""
    try:
        img = images.Image(blob_data)
        if height:
            img.resize(height=height)
        if width:
            img.resize(width=width)

        thumbnail = img.execute_transforms(output_encoding=images.PNG)
        res = u"""<img src='data:image/png;base64,%s' />""" % base64.encodestring(thumbnail)
    except BadImageError:
        pass
    except NotImageError:
        pass
    except NotImplementedError:
        pass

    return res

e = re.compile("[a-zA-Z]")

def is_in_english(s):
    return e.search(s)

h = re.compile(u"[א-ת]")

def is_in_hebrew(s):
    return h.search(s)

phone_regexp = re.compile(r'^[\*|\d]\d+$')
phone_validator = RegexValidator(phone_regexp, _(u"Value must consists of digits only."), 'invalid')

SingleRelatedObjectDescriptor = getattr(related, 'SingleRelatedObjectDescriptor')
ManyRelatedObjectsDescriptor = getattr(related, 'ManyRelatedObjectsDescriptor')
ForeignRelatedObjectsDescriptor = getattr(related, 'ForeignRelatedObjectsDescriptor')
related_class_list = [SingleRelatedObjectDescriptor, ManyRelatedObjectsDescriptor, ForeignRelatedObjectsDescriptor]

def get_related_fields(model):
    fields = []
    for attr in dir(model):
        if type(getattr(model, attr)) in related_class_list:
            fields.append(attr)
    return fields


def has_related_objects(model_instance):
    model = type(model_instance)
    related_fields = get_related_fields(model)
    has_related = True

    for field in related_fields:
        relation_type = type(getattr(model, field))

        if relation_type == SingleRelatedObjectDescriptor:
            try:
                getattr(model_instance, field)
                return False
            except Exception:
                continue

        if relation_type in [ManyRelatedObjectsDescriptor, ForeignRelatedObjectsDescriptor]:
            manager = getattr(model_instance, field)
            if manager.count() or manager.exists(): #TODO_WB: what is the difference?
                return False

    return has_related

def split_to_tuples(l, n):
    """
    Yield successive n-sized tuples from l.

    @param l: a list
    @param n: size of tuple
    @return: an iterator 
    """
    for i in xrange(0, len(l), n):
        yield tuple(l[i:i+n])


def split_to_chunks(l, n):
    """
    Yield successive n-sized chunks from l.

    @param l: a sequence
    @param n: size of tuple
    @return: an iterator
    """
    for i in xrange(0, len(l), n):
        yield l[i:i+n]

def point_inside_polygon(x,y,poly):

    n = len(poly)
    inside =False

    p1x,p1y = poly[0]
    for i in range(n+1):
        p2x,p2y = poly[i % n]
        if y > min(p1y,p2y):
            if y <= max(p1y,p2y):
                if x <= max(p1x,p2x):
                    if p1y != p2y:
                        xinters = (y-p1y)*(p2x-p1x)/(p2y-p1y)+p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
        p1x,p1y = p2x,p2y

    return inside

def point_inside_polygon_2(x, y, poly):
    nvert = len(poly)
    testx = x
    testy = y
    vertx = []
    verty = []
    for t in poly:
        valx, valy = t
        vertx.append(valx)
        verty.append(valy)
        
    i = 0
    j = nvert - 1
    c = False

    while i < nvert:
        if ((verty[i]>testy) != (verty[j]>testy)) and (testx < (vertx[j]-vertx[i]) * (testy-verty[i]) / (verty[j]-verty[i]) + vertx[i]):
            c = not c
        j = i
        i += 1

    return c

def get_text_from_element(node, *elements):
    """
    Tries to traverse the path of elements and retrieve the text node's data
    in the last element
    """
    for elem in elements:
        try:
            node = node.getElementsByTagName(elem)[0]
        except:
            return None

    if node.childNodes:
        if node.firstChild.data.isspace():
            return None
        else:
            return node.firstChild.data


def add_formatted_date_fields(classes):
    """
    For each DateTime in given model classes field add a methods to print the formatted date time according to
    settings.DATETIME_FORMAT
    """
    for model in classes:
        for f in model._meta.fields:
            if isinstance(f, models.DateTimeField):
                # create a wrapper function to force a new closure environment
                # so that iterator variable f will not be overwritten
                def format_datefield(field):
                    # actual formatter method
                    def do_format(self):
                        return getattr(self, field.name).strftime(settings.DATETIME_FORMAT)

                    do_format.admin_order_field = field.name
                    do_format.short_description = field.verbose_name
                    return do_format

                setattr(model, f.name + "_format", format_datefield(f))


