import random
from google.appengine.api import taskqueue
from google.appengine.api import mail
from google.appengine.api.images import BadImageError, NotImageError
from django.utils.translation import gettext as _
import logging
from django.shortcuts import render_to_response

class Enum:
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

class EventType(Enum):
    ORDER_BOOKED =                  1
    ORDER_ASSIGNED =                2
    ORDER_ACCEPTED =                3
    ORDER_REJECTED =                4
    ORDER_IGNORED =                 5
    ORDER_ERROR =                   6
    CROSS_COUNTRY_ORDER_FAILURE =   7
    NO_SERVICE_IN_CITY =            8
    NO_SERVICE_IN_COUNTRY =         9
    ORDER_FAILED =                  10
    ORDER_RATED =                   11
    UNREGISTERED_ORDER =            12
    PASSENGER_REGISTERED =          13

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


def is_empty(str):
    """
    return True pf string is empty, spaces only or None
    """
    return not str or len(str.strip()) == 0


# python weekdays (see: datetime.weekday()): monday=0 .. sunday=6
PYTHON_WEEKDAY_MAP = {
    6: 1,
    0: 2,
    1: 3,
    2: 4,
    3: 5,
    4: 6,
    5: 7
}

def convert_python_weekday(wd):
    return PYTHON_WEEKDAY_MAP[wd]

def gen_verification_code():
    return random.randrange(1000,10000)

def get_model_from_request(model_class, request):
        if (not request.user or not request.user.is_authenticated()):
            return None
        try:
            model_instance = model_class.objects.filter(user = request.user).get()
        except model_class.DoesNotExist:
            return None

        return model_instance


def log_event(event_type, order=None, order_assignment=None, station=None, work_station=None, passenger=None,
              country=None, city=None, rating="", lat="", lon=""):
    """
    Log a new analytics event asynchonically:
        event_type: an EventType field (e.g. EventType.ORDER_BOOKED)
        order, order_assignment, station, work_station, passenger: an optional instance 
    """
    if order: # fill values from order
        if not city:
            city = order.from_city
            country = order.from_country
            if order.from_city != order.to_city:
                log_event(event_type,
                          order=order,order_assignment=order_assignment,station=station, work_station=work_station,
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
    import hashlib
    import datetime
    s = hashlib.sha1()
    s.update(str(datetime.datetime.now()))
    return s.hexdigest()

def notify_by_email(subject, msg):
    logging.info(u"Sending email: [%s] %s" % (subject, msg))
    address = "notify@waybetter.com"
    try:
        mail.send_mail("guy@waybetter.com",
                       address,
                       subject,
                       msg)
    except :
        logging.error("Email sending failed.")

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
    except NotImageError :
        pass
    except NotImplementedError:
        pass

    return res