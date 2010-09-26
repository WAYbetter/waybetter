from django.db import models
from django.utils.translation import gettext_lazy as _, gettext
from django.conf import settings
from django.contrib.auth.models import User
from djangotoolbox.fields import BlobField
from common.models import Country, City, CityArea
from datetime import datetime

ASSIGNED = 1
ACCEPTED = 2
IGNORED = 3
REJECTED = 4
PENDING = 5
FAILED = 6
ERROR = 7

ASSIGNMENT_STATUS = ((ASSIGNED, gettext("assigned")),
                     (ACCEPTED, gettext("accepted")),
                     (IGNORED, gettext("ignored")),
                     (REJECTED, gettext("rejected")))


ORDER_STATUS = ASSIGNMENT_STATUS + ((PENDING, gettext("pending")),
                                    (FAILED, gettext("failed")),
                                    (ERROR, gettext("error")))


LANGUAGE_CHOICES = [(i, name) for i, (code, name) in enumerate(settings.LANGUAGES)]


class Passenger(models.Model):
    user = models.OneToOneField(User, verbose_name=_("user"), related_name="passenger")

    country = models.ForeignKey(Country, verbose_name=_("country"), related_name="passengers")
    phone = models.CharField(_("phone number"), max_length=15)
    phone_verified = models.BooleanField(_("phone verified"))
    phone_verification_code = models.CharField(_("phone verification code"), max_length=20)

    create_date = models.DateTimeField(_("create date"), auto_now_add=True)
    modify_date = models.DateTimeField(_("modify date"), auto_now=True)

    def __unicode__(self):
        return self.user.username

    @classmethod
    def get_passenger_from_request(cls, request):
        if (not request.user or not request.user.is_authenticated()):
            return None
        try:
            passenger = Passenger.objects.filter(user = request.user).get()
        except Passenger.DoesNotExist:
            return None

        return passenger

class Station(models.Model):
    user = models.OneToOneField(User, verbose_name=_("user"), related_name="station")
    name = models.CharField(_("station name"), max_length=50)
    license_number = models.CharField(_("license number"), max_length=30)
    website_url = models.URLField(_("website"), max_length=255 ,null=True,blank=True) #verify_exists=False
    number_of_taxis = models.IntegerField(_("number of taxis"), max_length=4)
    description = models.CharField(_("description"), max_length=4000,null=True,blank=True)
    logo = BlobField(_("logo"), null=True,blank=True)
    language  = models.IntegerField(_("language"), choices=LANGUAGE_CHOICES, default=0)

    # validator must ensure city.country == country and city_area = city.city_area
    country = models.ForeignKey(Country, verbose_name=_("country"), related_name="stations")
    city = models.ForeignKey(City, verbose_name=_("city"), related_name="stations")
    city_area = models.ForeignKey(CityArea, verbose_name=_("city area"), related_name="stations", null=True, blank=True)
    postal_code = models.CharField(_("postal code"), max_length=10)
    address = models.CharField(_("address"), max_length=80)
    geohash = models.CharField(_("goehash"), max_length=13)

    create_date = models.DateTimeField(_("create date"), auto_now_add=True)
    modify_date = models.DateTimeField(_("modify date"), auto_now=True)

    def natural_key(self):
        return self.name

    def __unicode__(self):
        return self.name

    def get_admin_link(self):
        return '<a href="%s/%d">%s</a>' % ('/admin/ordering/station', self.id, self.name)

class Phone(models.Model):
    country = models.ForeignKey(Country, verbose_name=_("country"), related_name="phones")
    local_phone = models.CharField(_("phone number"), max_length=15)

    station = models.ForeignKey(Station, verbose_name=_("station"), related_name="phones", null=True, blank=True)

    def __unicode__(self):
        return self.local_phone




class WorkStation(models.Model):
    user = models.OneToOneField(User, verbose_name=_("user"), related_name="work_station")

    station = models.ForeignKey(Station, verbose_name=_("station"), related_name="work_stations")
    token = models.CharField(_("token"), max_length=20)
    im_user = models.CharField(_("instant messaging username"), null=True, blank=True, max_length=40)
    accept_orders = models.BooleanField(_("Online"), default=True)

    def __unicode__(self):
        return u"Workstation "# of: %d" % (self.station.id)

    def get_admin_link(self):
        return '<a href="%s/%d">%s</a>' % ('/admin/ordering/workstation', self.id, self.user.username)


class Order(models.Model):

    passenger = models.ForeignKey(Passenger, verbose_name=_("passenger"), related_name="orders", null=True, blank=True)
    station = models.ForeignKey(Station, verbose_name=_("station"), related_name="orders", null=True, blank=True)

    status = models.IntegerField(_("status"), choices=ORDER_STATUS, default=PENDING)

    from_country = models.ForeignKey(Country, verbose_name=_("from country"), related_name="orders_from")
    from_city = models.ForeignKey(City, verbose_name=_("from city"), related_name="orders_from")
    from_city_area = models.ForeignKey(CityArea, verbose_name=_("from city area"), related_name="orders_from", null=True, blank=True)
    from_postal_code = models.CharField(_("from postal code"), max_length=10, null=True, blank=True)
    from_street_address = models.CharField(_("from street address"), max_length=50)
    from_geohash = models.CharField(_("from goehash"), max_length=13)
    from_lon = models.FloatField(_("from_lon"))
    from_lat = models.FloatField(_("from_lat"))
    from_raw = models.CharField(_("from address"), max_length=50)
    # this field holds the data as typed by the user
    to_country = models.ForeignKey(Country, verbose_name=_("to country"), related_name="orders_to")

    to_city = models.ForeignKey(City, verbose_name=_("to city"), related_name="orders_to")
    to_city_area = models.ForeignKey(CityArea, verbose_name=_("to city area"), related_name="orders_to", null=True, blank=True)
    to_postal_code = models.CharField(_("to postal code"), max_length=10, null=True, blank=True)
    to_street_address = models.CharField(_("to street address"), max_length=50)
    to_geohash = models.CharField(_("to goehash"), max_length=13)
    to_lon = models.FloatField(_("to_lon"))
    to_lat = models.FloatField(_("to_lat"))
    # this field holds the data as typed by the user
    to_raw = models.CharField(_("to address"), max_length=50)

    pickup_time = models.IntegerField(_("pickup time"), null=True, blank=True)

    create_date = models.DateTimeField(_("create date"), auto_now_add=True)
    modify_date = models.DateTimeField(_("modify date"), auto_now=True)
    
    def __unicode__(self):
        return u"%s from %s to %s" % (_("order"), self.from_raw, self.to_raw)

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

    
class OrderAssignment(models.Model):
    ORDER_ASSIGNMENT_TIMEOUT = 11 # seconds 

    order = models.ForeignKey(Order, verbose_name=_("order"), related_name="assignments")
    work_station = models.ForeignKey(WorkStation, verbose_name=_("work station"), related_name="assignments")
    station = models.ForeignKey(Station, verbose_name=_("station"), related_name="assignments")
    
    status = models.IntegerField(_("status"), choices=ASSIGNMENT_STATUS, default=ASSIGNED)

    create_date = models.DateTimeField(_("create date"), auto_now_add=True)
    modify_date = models.DateTimeField(_("modify date"), auto_now=True)

    def is_stale(self):
         return (datetime.now() - self.create_date).seconds > OrderAssignment.ORDER_ASSIGNMENT_TIMEOUT

    def __unicode__(self):
        order_id = "Unknown"
        if self.order:
            order_id =str(self.order)
            
        return u"%s #%s %s %s" % (_("order"), order_id, _("assigned to station:"), self.station)


DAY_OF_WEEK_CHOICES = ((1, _("Sunday")),
                       (2, _("Monday")),
                       (3, _("Tuesday")),
                       (4, _("Wednesday")),
                       (5, _("Thurday")),
                       (6, _("Friday")),
                       (7, _("Saturday")))

VEHICLE_TYPE_CHOICES = ((1, _("Standard cab")),)

class PricingRule(models.Model):
    """
    Used to calculate the estimated cost of a ride.
    Pricing Rules need to cover the relevant pricing model in
    each country's regulation of taxi transportation.
    The algorithm selects all rules applying to a given ride
    that the passenger wishes to order, &amp; calculates the
    total estimated cost based on these rules.
    """
    rule_name = models.CharField(_("name"), max_length=500)
    is_active = models.BooleanField(_("is active"), default=True)
    # geographic predicates
    country = models.ForeignKey(Country, verbose_name=_("country"), related_name="pricing_rules")
    state = models.CharField(_("state"), max_length=100, null=True, blank=True)
    city = models.ForeignKey(City, verbose_name=_("city"), related_name="pricing_rules", null=True, blank=True)
    city_area = models.ForeignKey(CityArea, verbose_name=_("city area"), related_name="pricing_rules", null=True, blank=True)
    special_place = models.CharField(_("special place"), max_length=100, null=True, blank=True, help_text=_("Such as an airport or toll-road inflicting extra charges"))
    # time predicates
    from_hour = models.TimeField(_("from hour"), null=True, blank=True)
    to_hour = models.TimeField(_("to hour"), null=True, blank=True)
    from_day_of_week = models.IntegerField(_("from day-of-week"), choices=DAY_OF_WEEK_CHOICES, null=True, blank=True)
    to_day_of_week = models.IntegerField(_("to day-of-week"), choices=DAY_OF_WEEK_CHOICES, null=True, blank=True)
    # vehicle type predicates
    vehicle_type = models.IntegerField(_("vehicle type"), choices=VEHICLE_TYPE_CHOICES, null=True, blank=True)
    # distance predicates
    from_distance = models.FloatField(_("from distance (m)"), null=True, blank=True, help_text=_("in meters"))
    to_distance = models.FloatField(_("to distance (m)"), null=True, blank=True, help_text=_("in meters"))
    # time predicates
    from_duration = models.IntegerField(_("from duration (s)"), null=True, blank=True, help_text=_("in seconds"))
    to_duration = models.IntegerField(_("to duration (s)"), null=True, blank=True, help_text=_("in seconds"))

    # cost
    fixed_cost = models.FloatField(_("fixed cost"), null=True, blank=True)
    tick_distance = models.FloatField(_("tick distance (m)"), null=True, blank=True, help_text=_("In meters"))
    tick_time = models.IntegerField(_("tick time (s)"), null=True, blank=True, help_text=_("In seconds"))
    tick_cost = models.FloatField(_("cost per tick"), null=True, blank=True)

    create_date = models.DateTimeField(_("create date"), auto_now_add=True)
    modify_date = models.DateTimeField(_("modify date"), auto_now=True)

    def __unicode__(self):
        return self.rule_name
