from django.db.models.query import QuerySet
from django.db import models
from django.utils.translation import gettext_lazy as _, gettext, ugettext
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import simplejson
from djangotoolbox.fields import BlobField
from common.models import Country, City, CityArea
from datetime import datetime
import time
from common.geo_calculations import distance_between_points
from common.util import get_international_phone, generate_random_token, notify_by_email, get_model_from_request
import re
from django.core.validators import RegexValidator
import common.urllib_adaptor as urllib2
import urllib
import logging

ASSIGNED = 1
ACCEPTED = 2
IGNORED = 3
REJECTED = 4
PENDING = 5
FAILED = 6
ERROR = 7

ASSIGNMENT_STATUS = ((ASSIGNED, ugettext("assigned")),
                     (ACCEPTED, ugettext("accepted")),
                     (IGNORED, ugettext("ignored")),
                     (REJECTED, ugettext("rejected")))

ORDER_STATUS = ASSIGNMENT_STATUS + ((PENDING, ugettext("pending")),
                                    (FAILED, ugettext("failed")),
                                    (ERROR, ugettext("error")))

LANGUAGE_CHOICES = [(i, name) for i, (code, name) in enumerate(settings.LANGUAGES)]

MAX_STATION_DISTANCE_KM = 10
CURRENT_PASSENGER_KEY = "current_passenger"


def add_formatted_create_date(classes):
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

class Station(models.Model):
    user = models.OneToOneField(User, verbose_name=_("user"), related_name="station")
    name = models.CharField(_("station name"), max_length=50)
    license_number = models.CharField(_("license number"), max_length=30)
    website_url = models.URLField(_("website"), max_length=255, null=True, blank=True, verify_exists=False)
    number_of_taxis = models.IntegerField(_("number of taxis"), max_length=4)
    description = models.TextField(_("description"), max_length=5000, null=True, blank=True)
    logo = BlobField(_("logo"), null=True, blank=True)
    language = models.IntegerField(_("language"), choices=LANGUAGE_CHOICES, default=0)
    show_on_list = models.BooleanField(_("show on list"), default=False)

    last_assignment_date = models.DateTimeField(_("last order date"), null=True, blank=True, default=datetime(1,1,1))

    # validator must ensure city.country == country and city_area = city.city_area
    country = models.ForeignKey(Country, verbose_name=_("country"), related_name="stations")
    city = models.ForeignKey(City, verbose_name=_("city"), related_name="stations")
    city_area = models.ForeignKey(CityArea, verbose_name=_("city area"), related_name="stations", null=True, blank=True)
    postal_code = models.CharField(_("postal code"), max_length=10)
    address = models.CharField(_("address"), max_length=80)
    geohash = models.CharField(_("goehash"), max_length=13)
    lon = models.FloatField(_("longtitude"), null=True)
    lat = models.FloatField(_("latitude"), null=True)

    number_of_ratings = models.IntegerField(_("number of ratings"), default=0)
    average_rating = models.FloatField(_("average rating"), default=0.0)

    create_date = models.DateTimeField(_("create date"), auto_now_add=True)
    modify_date = models.DateTimeField(_("modify date"), auto_now=True)

    def natural_key(self):
        return self.name

    def __unicode__(self):
        return u"%s" % self.name

    def get_admin_link(self):
        return '<a href="%s/%d">%s</a>' % ('/admin/ordering/station', self.id, self.name)

    def is_in_valid_distance(self, from_lon, from_lat, to_lon, to_lat):
        if not (self.lat and self.lon): # ignore station with unknown address
            return False
        to_distance = MAX_STATION_DISTANCE_KM + 1
        from_distance = distance_between_points(self.lat, self.lon, from_lat, from_lon)
        if to_lon and to_lat:
            to_distance = distance_between_points(self.lat, self.lon, to_lat, to_lon)

        return from_distance <= MAX_STATION_DISTANCE_KM or to_distance <= MAX_STATION_DISTANCE_KM 

    @staticmethod
    def get_default_station_choices(order_by="name", include_empty_option=True):
        choices = [(-1, "-----------")] if include_empty_option else []
        choices.extend([(station.id, station.name) for station in Station.objects.all().order_by(order_by)])
        return choices


    def create_workstation(self, index):
        username = "%s_workstation_%d" % (self.user.username, index)
        password = generate_random_token(alpha_or_digit_only=True)
        ws_user, created = User.objects.get_or_create(username=username)
        if created:
            ws_user.email = self.user.email
            ws_user.set_password(password)
            ws_user.save()

        ws, ws_created = WorkStation.objects.get_or_create(user=ws_user, station=self)
        if ws_created:
            ws.save() # trigger build of installer
            logging.debug("Created workstation: %s" % username)


    def build_workstations(self):
        for i in range(0, settings.NUMBER_OF_WORKSTATIONS_TO_CREATE):
            self.create_workstation(i+1)

    def delete_workstations(self):
        self.work_stations.all().delete()

class Passenger(models.Model):
    user = models.OneToOneField(User, verbose_name=_("user"), related_name="passenger", null=True, blank=True)

    country = models.ForeignKey(Country, verbose_name=_("country"), related_name="passengers")
    default_station = models.ForeignKey(Station, verbose_name=_("Default station"), related_name="default_passengers",
                                        default=None, null=True, blank=True)

    phone = models.CharField(_("phone number"), max_length=15)
    phone_verified = models.BooleanField(_("phone verified"))
    phone_verification_code = models.CharField(_("phone verification code"), max_length=20)

    create_date = models.DateTimeField(_("create date"), auto_now_add=True)
    modify_date = models.DateTimeField(_("modify date"), auto_now=True)

    def international_phone(self):
        return get_international_phone(self.country, self.phone)

    def is_internal_passenger(self):
        """
        Return True if the passenger's user was registered internally
        """
        result = True
        if self.user and self.user.authmeta_set.all().count():
            result = False

        return result

    @classmethod
    def from_request(cls, request):
        passenger = get_model_from_request(cls, request)
        if not passenger:
            passenger = request.session.get(CURRENT_PASSENGER_KEY, None)
        return passenger
  

    def __unicode__(self):
        return u"Passenger: %s, %s" % (self.phone, self.user.username if self.user else "[UNKNOWN USER]")

digits_re = re.compile(r'^\d+$')
validate_digits = RegexValidator(digits_re, _(u"Value must consists of digits only."), 'invalid')
class Phone(models.Model):
    local_phone = models.CharField(_("phone number"), max_length=20, validators=[validate_digits])

    station = models.ForeignKey(Station, verbose_name=_("station"), related_name="phones", null=True, blank=True)


    def __unicode__(self):
        if self.local_phone:
            return u"%s" % self.local_phone
        else:
            return u""

class WorkStation(models.Model):
    user = models.OneToOneField(User, verbose_name=_("user"), related_name="work_station")

    station = models.ForeignKey(Station, verbose_name=_("station"), related_name="work_stations")
    token = models.CharField(_("token"), max_length=50, null=True, blank=True)
    installer_url = models.URLField(_("installer URL"), verify_exists=False, max_length=500, null=True, blank=True)
    was_installed = models.BooleanField(_("was installed"), default=False)
    im_user = models.CharField(_("instant messaging username"), null=True, blank=True, max_length=40)
    accept_orders = models.BooleanField(_("Accept orders"), default=True)

    last_assignment_date = models.DateTimeField(_("last order date"), null=True, blank=True, default=datetime(1,1,1))

    def __unicode__(self):
        result = u"[%d]" % self.id
        try:
            result += u" user=%s" % self.user.username
        except User.DoesNotExist:
            pass

        try:
            result += u" station=%s" % self.station.name
        except Station.DoesNotExist:
            pass

        return result 

    def get_admin_link(self):
        return '<a href="%s/%d">%s</a>' % ('/admin/ordering/workstation', self.id, self.user.username)

    def fetch_installer_URL(self):
        """
        Invokes the get_installer_url service in the AIR build service,
        providing it the workstation token.
        """
        if self.token is None:
            raise RuntimeError("No token found for the workstation")
        url = "%get_installer/?token=%s" % (settings.BUILD_SERVICE_BASE_URL)
        installer_url = urllib2.urlopen(url).read()
        self.installer_url = installer_url
        self.save()
        return self.installer_url


    def build_installer(self):
        """
        Invokes the build_installer_url service in the AIR build service,
        providing it the workstation token.
        """
        if self.token is None or len(self.token) == 0:
            self.token = generate_random_token(alpha_or_digit_only=True)
        if self.installer_url is None or len(self.installer_url) == 0:
            try:
                url = "%sbuild_installer/" % settings.BUILD_SERVICE_BASE_URL
                data = {"token": self.token, "workstation_id": self.id}
                params = urllib.urlencode(data)
                installer_url = urllib2.urlopen(url, params).read()
                self.installer_url = installer_url
                self.save()
            except:
                time.sleep(5)
                url = "%sget_installer/?token=%s" % (settings.BUILD_SERVICE_BASE_URL, self.token)
                installer_url = urllib2.urlopen(url).read()
                self.installer_url = installer_url
                self.save()

        return self.installer_url


def build_installer_for_workstation(sender, instance, **kwargs):
    instance.build_installer()


models.signals.post_save.connect(build_installer_for_workstation, sender=WorkStation)

RATING_CHOICES = ((1, gettext("Very poor")),
                  (2, gettext("Not so bad")),
                  (3, gettext("Average")),
                  (4, gettext("Good")),
                  (5, gettext("Perfect")))

class Order(models.Model):
    passenger = models.ForeignKey(Passenger, verbose_name=_("passenger"), related_name="orders", null=True, blank=True)
    station = models.ForeignKey(Station, verbose_name=_("station"), related_name="orders", null=True, blank=True)

    status = models.IntegerField(_("status"), choices=ORDER_STATUS, default=PENDING)

    from_country = models.ForeignKey(Country, verbose_name=_("from country"), related_name="orders_from")
    from_city = models.ForeignKey(City, verbose_name=_("from city"), related_name="orders_from")
    from_city_area = models.ForeignKey(CityArea, verbose_name=_("from city area"), related_name="orders_from", null=True
                                       , blank=True)
    from_postal_code = models.CharField(_("from postal code"), max_length=10, null=True, blank=True)
    from_street_address = models.CharField(_("from street address"), max_length=50)
    from_geohash = models.CharField(_("from goehash"), max_length=13)
    from_lon = models.FloatField(_("from_lon"))
    from_lat = models.FloatField(_("from_lat"))
    # this field holds the data as typed by the user
    from_raw = models.CharField(_("from address"), max_length=50)

    to_country = models.ForeignKey(Country, verbose_name=_("to country"), related_name="orders_to", null=True, blank=True)
    to_city = models.ForeignKey(City, verbose_name=_("to city"), related_name="orders_to", null=True, blank=True)
    to_city_area = models.ForeignKey(CityArea, verbose_name=_("to city area"), related_name="orders_to", null=True,
                                     blank=True)
    to_postal_code = models.CharField(_("to postal code"), max_length=10, null=True, blank=True)
    to_street_address = models.CharField(_("to street address"), max_length=50, null=True, blank=True)
    to_geohash = models.CharField(_("to goehash"), max_length=13, null=True, blank=True)
    to_lon = models.FloatField(_("to_lon"), null=True, blank=True)
    to_lat = models.FloatField(_("to_lat"), null=True, blank=True)
    # this field holds the data as typed by the user
    to_raw = models.CharField(_("to address"), max_length=50, null=True, blank=True)

    pickup_time = models.IntegerField(_("pickup time"), null=True, blank=True)

    passenger_rating = models.IntegerField(_("passenger rating"), choices=RATING_CHOICES, null=True, blank=True)

    create_date = models.DateTimeField(_("create date"), auto_now_add=True)
    modify_date = models.DateTimeField(_("modify date"), auto_now=True)

    # denormalized fields
    station_name = models.CharField(_("station name"), max_length=50, null=True, blank=True)
    station_id = models.IntegerField(_("station id"), null=True, blank=True)
    passenger_phone = models.CharField(_("passenger phone"), max_length=50, null=True, blank=True)
    passenger_id = models.IntegerField(_("passenger id"), null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.station:
            self.station_id = self.station.id
            self.station_name = self.station.name
        else:
            self.station_id = None
            self.station_name = ""
        if self.passenger:
            self.passenger_id = self.passenger.id
            self.passenger_phone = self.passenger.phone
        else:
            self.passenger_id = None
            self.passenger_phone = ""

        super(Order, self).save(*args, **kwargs)


    def __unicode__(self):
        id = self.id
        if self.to_raw:
            return u"[%d] %s from %s to %s" % (id, ugettext("order"), self.from_raw, self.to_raw)
        else:
            return u"[%d] %s from %s" % (id, ugettext("order"), self.from_raw)

    def get_status_label(self):
        for key, label in ORDER_STATUS:
            if key == self.status:
                return label

        raise ValueError("invalid status")

    def get_station(self):
        assignments = OrderAssignment.objects.filter(order=self)
        if assignments.count() > 0:
            for oa in assignments:
                if oa.status == ACCEPTED:
                    return oa.station
        return None

    def notify(self):
        subject = u"Order [%d]: %s" % (self.id, self.get_status_label().upper())
        msg = u"""Order %d:
    Passenger:  %s
    Created:    %s
    From:       %s
    To:         %s.""" % (self.id,  unicode(self.passenger), self.create_date.ctime(), self.from_raw, self.to_raw)

        if self.status == ACCEPTED:
            msg += u"""
    Station:    %s
    Pickup in:  %d minutes""" % (self.station.name, self.pickup_time)

        if self.assignments.count():
            msg += u"\n\nEvents:"
            for assignment in self.assignments.all():
                msg+= u"\n%s: %s - %s" % (assignment.modify_date.ctime(), assignment.station.name, assignment.get_status_label().upper())
            
        notify_by_email(subject, msg)

class OrderAssignment(models.Model):
    ORDER_ASSIGNMENT_TIMEOUT = 120 # seconds

    order = models.ForeignKey(Order, verbose_name=_("order"), related_name="assignments")
    work_station = models.ForeignKey(WorkStation, verbose_name=_("work station"), related_name="assignments")
    station = models.ForeignKey(Station, verbose_name=_("station"), related_name="assignments")

    status = models.IntegerField(_("status"), choices=ASSIGNMENT_STATUS, default=ASSIGNED)

    create_date = models.DateTimeField(_("create date"), auto_now_add=True)
    modify_date = models.DateTimeField(_("modify date"), auto_now=True)

    @classmethod
    def serialize_for_workstation(cls, queryset_or_order_assignment):
        if isinstance(queryset_or_order_assignment, QuerySet):
            order_assignments = queryset_or_order_assignment
        elif isinstance(queryset_or_order_assignment, cls):
            order_assignments = [queryset_or_order_assignment]
        else:
            raise RuntimeError("Argument must be either QuerySet or %s" % cls.__name__)

        result = []
        for order_assignment in order_assignments:
            result.append({
                "pk":               order_assignment.order.id,
                "from_raw":         order_assignment.order.from_raw,
                "seconds_passed":   (datetime.now() - order_assignment.create_date).seconds
            })

        return simplejson.dumps(result)

    def get_status_label(self):
        for key, label in ASSIGNMENT_STATUS:
            if key == self.status:
                return label

        raise ValueError("invalid status")


    def is_stale(self):
        return (datetime.now() - self.create_date).seconds > OrderAssignment.ORDER_ASSIGNMENT_TIMEOUT

    def __unicode__(self):
        order_id = "<Unknown>"
        if self.order:
            order_id = u"<%d>" % self.order.id
            
        return u"%s %s %s %s" % (ugettext("order"), order_id, ugettext("assigned to station:"), self.station)


DAY_OF_WEEK_CHOICES = ((1, _("Sunday")),
                       (2, _("Monday")),
                       (3, _("Tuesday")),
                       (4, _("Wednesday")),
                       (5, _("Thursday")),
                       (6, _("Friday")),
                       (7, _("Saturday")))

VEHICLE_TYPE_CHOICES = ((1, _("Standard cab")),)

# time and distance dependent rules (meter)
class MeteredRateRule(models.Model):
    rule_name = models.CharField(_("name"), max_length=500)
    is_active = models.BooleanField(_("is active"), default=True)
    country = models.ForeignKey(Country, verbose_name=_("country"), related_name="metered_rules")

    # time predicates
    from_day = models.IntegerField(_("from day"), choices=DAY_OF_WEEK_CHOICES, null=True, blank=True)
    to_day = models.IntegerField(_("to day"), choices=DAY_OF_WEEK_CHOICES, null=True, blank=True)
    from_hour = models.TimeField(_("from hour"), null=True, blank=True)
    to_hour = models.TimeField(_("to hour"), null=True, blank=True)

    from_duration = models.IntegerField(_("from duration (s)"), null=True, blank=True, help_text=_("In seconds"))
    to_duration = models.IntegerField(_("to duration (s)"), null=True, blank=True, help_text=_("In seconds"))

    # distance predicates
    from_distance = models.FloatField(_("from distance (m)"), null=True, blank=True, help_text=_("In meters"))
    to_distance = models.FloatField(_("to distance (m)"), null=True, blank=True, help_text=_("In meters"))

    # cost
    tick_distance = models.FloatField(_("tick distance (m)"), null=True, blank=True, help_text=_("In meters"))
    tick_time = models.IntegerField(_("tick time (s)"), null=True, blank=True, help_text=_("In seconds"))
    tick_cost = models.FloatField(_("cost per tick"), null=True, blank=True)
    fixed_cost = models.FloatField(_("fixed cost"), null=True, blank=True)
    
    create_date = models.DateTimeField(_("create date"), auto_now_add=True)
    modify_date = models.DateTimeField(_("modify date"), auto_now=True)

    def __unicode__(self):
        return self.rule_name

# rules with flat rate (e.g., from city to another city or airport)
class FlatRateRule(models.Model):
    rule_name = models.CharField(_("name"), max_length=500)
    is_active = models.BooleanField(_("is active"), default=True)
    country = models.ForeignKey(Country, verbose_name=_("country"), related_name="flat_rate_rules")

    city1 = models.ForeignKey(City, verbose_name=_("city 1"), related_name="flat_rate_rule_city1")
    city2 = models.ForeignKey(City, verbose_name=_("city 2"), related_name="flat_rate_rule_city2")

    from_hour = models.TimeField(_("from hour"), null=True, blank=True)
    to_hour = models.TimeField(_("to hour"), null=True, blank=True)
    from_day = models.IntegerField(_("from day-of-week"), choices=DAY_OF_WEEK_CHOICES, null=True, blank=True)
    to_day = models.IntegerField(_("to day-of-week"), choices=DAY_OF_WEEK_CHOICES, null=True, blank=True)

    fixed_cost = models.FloatField(_("fixed cost"))

    create_date = models.DateTimeField(_("create date"), auto_now_add=True)
    modify_date = models.DateTimeField(_("modify date"), auto_now=True)

    def __unicode__(self):
        return "from %s to %s" % (self.city1.name,self.city2.name)

# rules for extra charges (e.g., phone order)
class ExtraChargeRule(models.Model):
    rule_name = models.CharField(_("name"), max_length=500)
    is_active = models.BooleanField(_("is active"), default=True)
    country = models.ForeignKey(Country, verbose_name=_("country"), related_name="extra_charge_rules")
 
    cost = models.FloatField(_("fixed cost"))

    create_date = models.DateTimeField(_("create date"), auto_now_add=True)
    modify_date = models.DateTimeField(_("modify date"), auto_now=True)

    def __unicode__(self):
        return self.rule_name

FEEDBACK_CATEGORIES =       ["Website", "Booking", "Registration", "Taxi Ride", "Other"]
FEEDBACK_CATEGORIES_NAMES = [_("Website"), _("Booking"), _("Registration"), _("Taxi Ride"), _("Other")]
FEEDBACK_TYPES =            ["Positive", "Negative"]

class Feedback(models.Model):
    passenger = models.ForeignKey(Passenger, verbose_name=_("passenger"), related_name="feedbacks", null=True, blank=True)

    def __unicode__(self):
        attributes = []
        for category in FEEDBACK_CATEGORIES:
            for type in FEEDBACK_TYPES:
                attr_name = "%s_%s" % (type.lower(), category.lower().replace(" ", "_"))
                if getattr(self, attr_name):
                    attributes.append(u"%s %s" % (type, category))

        return u"%s: %s" % (self.__class__.__name__, u", ".join(attributes))
  
    @staticmethod
    def field_names():
        field_names = []
        for category in FEEDBACK_CATEGORIES:
            for type in FEEDBACK_TYPES:
                field_names.append("%s_%s" % (type.lower(), category.lower().replace(" ", "_")))

        return field_names

for i, category in zip(range(len(FEEDBACK_CATEGORIES)), FEEDBACK_CATEGORIES):
    for type in FEEDBACK_TYPES:
        models.CharField(FEEDBACK_CATEGORIES_NAMES[i], max_length=100, null=True, blank=True).contribute_to_class(Feedback, "%s_%s_msg" % (type.lower(), category.lower().replace(" ", "_")))
        models.BooleanField(default=False).contribute_to_class(Feedback, "%s_%s" % (type.lower(), category.lower().replace(" ", "_")))

add_formatted_create_date([Order, OrderAssignment, Passenger, Station, WorkStation])