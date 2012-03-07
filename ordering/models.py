# -*- coding: utf-8 -*-

from __future__ import absolute_import
from django.core.exceptions import ValidationError
from django.template.loader import get_template
from django.template.context import Context
from google.appengine.ext.db import is_in_transaction
from api.models import APIUser
from django.db.models.query import QuerySet
from django.db import models
from django.utils.translation import ugettext_lazy as _, ugettext
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.utils import  translation
from django.contrib.auth import login
from djangotoolbox.fields import BlobField, ListField
from common.models import BaseModel, Country, City, CityArea, CityAreaField, obj_by_attr
from common.geo_calculations import distance_between_points
from common.util import get_international_phone, generate_random_token, notify_by_email, send_mail_as_noreply, get_model_from_request, phone_validator, StatusField, get_channel_key, Enum, DAY_OF_WEEK_CHOICES, generate_random_token_64
from common.tz_support import UTCDateTimeField, utc_now, to_js_date, default_tz_now, format_dt
from ordering.signals import order_status_changed_signal, orderassignment_status_changed_signal, workstation_offline_signal, workstation_online_signal
from ordering.errors import UpdateStatusError
from sharing.signals import ride_status_changed_signal
from pricing.models import RuleSet

import re
import time
import urllib
import logging
import datetime
import common.urllib_adaptor as urllib2

SHARING_TIME_FACTOR = 1.25
SHARING_TIME_MINUTES = 7

ORDER_HANDLE_TIMEOUT =                      80 # seconds
ORDER_TEASER_TIMEOUT =                      19 # seconds
ORDER_ASSIGNMENT_TIMEOUT =                  80 # seconds
WORKSTATION_HEARTBEAT_TIMEOUT_INTERVAL =    60 # seconds
RIDE_SENTINEL_GRACE = datetime.timedelta(minutes=7)

ORDER_MAX_WAIT_TIME = ORDER_HANDLE_TIMEOUT + ORDER_ASSIGNMENT_TIMEOUT
UNKNOWN_USER = "[UNKNOWN USER]"
PASSENGER_TOKEN = "passenger_token"

ASSIGNED = 1
ACCEPTED = 2
IGNORED = 3
REJECTED = 4
PENDING = 5
FAILED = 6
ERROR = 7
NOT_TAKEN = 8
TIMED_OUT = 9
COMPLETED = 10
CANCELLED = 11
APPROVED = 12 # J5
CHARGED = 13 # J4

ASSIGNMENT_STATUS = ((PENDING, ugettext("pending")),
                     (ASSIGNED, ugettext("assigned")),
                     (ACCEPTED, ugettext("accepted")),
                     (IGNORED, ugettext("ignored")),
                     (REJECTED, ugettext("rejected")),
                     (NOT_TAKEN, ugettext("not_taken")))

ORDER_STATUS = ASSIGNMENT_STATUS + ((FAILED, ugettext("failed")),
                                    (ERROR, ugettext("error")),
                                    (TIMED_OUT, ugettext("timed_out")),
                                    (CANCELLED, ugettext("cancelled")),
                                    (APPROVED, ugettext("approved")),
                                    (CHARGED, ugettext("charged")))

SHARED_RIDE_STATUS = ((PENDING, ugettext("pending")),
                     (ASSIGNED, ugettext("assigned")),
                     (COMPLETED, ugettext("completed")),
                     (ACCEPTED, ugettext("accepted")),
                     (NOT_TAKEN, ugettext("not_taken")))

LANGUAGE_CHOICES = [(i, name) for i, (code, name) in enumerate(settings.LANGUAGES)]

MAX_STATION_DISTANCE_KM = 10
CURRENT_PASSENGER_KEY = "current_passenger"
CURRENT_ORDER_KEY = "current_order"

class RideComputationStatus(Enum):
    PENDING     = 1
    SUBMITTED   = 2
    COMPLETED   = 3
    ABORTED     = 4
    PROCESSING  = 5
    IGNORED     = 6

class StopType(Enum):
    PICKUP  = 0
    DROPOFF = 1

class OrderType(Enum):
    PICKMEAPP     = 0
    PRIVATE       = 1
    SHARED        = 2

class Station(BaseModel):
    user = models.OneToOneField(User, verbose_name=_("user"), related_name="station")
    name = models.CharField(_("station name"), max_length=50)
    license_number = models.CharField(_("license number"), max_length=30)
    website_url = models.URLField(_("website"), max_length=255, null=True, blank=True)
    number_of_taxis = models.IntegerField(_("number of taxis"), max_length=4)
    description = models.TextField(_("description"), max_length=5000, null=True, blank=True)
    logo = BlobField(_("logo"), null=True, blank=True)
    language = models.IntegerField(_("language"), choices=LANGUAGE_CHOICES, default=0)
    show_on_list = models.BooleanField(_("show on list"), default=False)
    subdomain_name = models.CharField(_("subdomain name"), max_length=50, blank=True, null=True, unique=True)
    app_icon_url = models.URLField(_("app icon"), max_length=255, null=True, blank=True)
    app_splash_url = models.URLField(_("app splash"), max_length=255, null=True, blank=True)

    unique_id = models.CharField(_("unique id"), max_length=64, default=generate_random_token_64, editable=False)
    itunes_app_url = models.URLField(max_length=255, null=True, blank=True)
    market_app_url = models.URLField(max_length=255, null=True, blank=True)

    last_assignment_date = UTCDateTimeField(_("last order date"), null=True, blank=True,
                                            default=datetime.datetime(1, 1, 1))

    confine_orders = models.BooleanField(_("confine orders"), default=False)
    sms_drivers = models.BooleanField(_("send sms to drivers"), default=False)
    vouchers_emails = models.CharField(_("voucher emails"), max_length=255, null=True, blank=True)

    # validator must ensure city.country == country and city_area = city.city_area
    country = models.ForeignKey(Country, verbose_name=_("country"), related_name="stations")
    city = models.ForeignKey(City, verbose_name=_("city"), related_name="stations")
    city_area = models.ForeignKey(CityArea, verbose_name=_("city area"), related_name="stations", null=True, blank=True)
    postal_code = models.CharField(_("postal code"), max_length=10)
    address = models.CharField(_("address"), max_length=80)
    geohash = models.CharField(_("goehash"), max_length=13)
    lon = models.FloatField(_("longtitude"), null=True)
    lat = models.FloatField(_("latitude"), null=True)

    app_icon_url = models.URLField(_("app icon"), max_length=255, null=True, blank=True)
    app_splash_url = models.URLField(_("app splash"), max_length=255, null=True, blank=True)

    number_of_ratings = models.IntegerField(_("number of ratings"), default=0)
    average_rating = models.FloatField(_("average rating"), default=0.0)
    internal_rating = models.FloatField(_("internal rating"), default=0)

    stop_price = models.FloatField(_("stop price"), default=0)
    payday = models.IntegerField(_("payday"), max_length=2, default=10) # day of month the drivers get paid

    page_description = models.CharField(_("page description"), null=True, blank=True, max_length=255)
    page_keywords = models.CharField(_("page keywords"), null=True, blank=True, max_length=255)

    application_terms = models.TextField(_("application terms"), max_length=5000, null=True, blank=True)


    @property
    def phone(self):
        return self.phones.all()[0].local_phone
    
    def natural_key(self):
        return self.name

    def __unicode__(self):
        return u"%s" % self.name

    def get_admin_link(self):
        return '<a href="%s/%d">%s</a>' % ('/admin/ordering/station', self.id, self.name)

    def get_station_page_link(self):
        if self.subdomain_name:
            return "http://%s.taxiapp.co.il" % self.subdomain_name
        else:
            return "http://taxiapp.co.il"

    def get_ride_price(self, shared_ride, rules_only=False):
        """
        Get the station's pricing for a shared ride.
        @param shared_ride: a SharedRide
        @return: the price, or None if price is not defined for all orders of the shared ride.
        """
        orders = set(shared_ride.orders.all())
        priced_orders = set()
        price_rules = set()
        for rule in self.fixed_prices.all():
            for order in orders:
                if rule.is_active(order.pickup_point.lat, order.pickup_point.lon, order.dropoff_point.lat, order.dropoff_point.lon, shared_ride.depart_time.date(), shared_ride.depart_time.time()):
                    price_rules.add(rule)
                    priced_orders.add(order)

        if rules_only:
            return price_rules
        elif price_rules and priced_orders == orders:
            return max([pr.price for pr in price_rules]) + self.stop_price * shared_ride.charged_stops
        else:
            return None

    def is_in_valid_distance(self, order=None, from_lon=None, from_lat=None, to_lon=None, to_lat=None):
        if not (self.lat and self.lon): # ignore station with unknown address
            return False

        distance = float("inf")

        if order:
            distance = self.distance_from_order(order=order, to_pickup=True, to_dropoff=True)
        else:
            if from_lon and from_lat:
                distance = distance_between_points(self.lat, self.lon, from_lat, from_lon)
            if to_lon and to_lat:
                distance = min(distance, distance_between_points(self.lat, self.lon, to_lat, to_lon))

        return distance <= MAX_STATION_DISTANCE_KM if distance < float("inf") else False

    def distance_from_order(self, order, to_pickup, to_dropoff):
        pickup_distance, dropoff_distance = float("inf"), float("inf")

        if to_pickup and order.from_lat and order.from_lon:
            pickup_distance = distance_between_points(self.lat, self.lon, order.from_lat, order.from_lon)

        if to_dropoff and order.to_lat and order.to_lon:
            dropoff_distance = distance_between_points(self.lat, self.lon, order.to_lat, order.to_lon)

        return min(pickup_distance, dropoff_distance)

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
#            ws.save() # trigger build of installer
            ws.build_installer()
            logging.debug("Created workstation: %s" % username)


    def build_workstations(self):
        for i in range(0, settings.NUMBER_OF_WORKSTATIONS_TO_CREATE):
            self.create_workstation(i + 1)

    def delete_workstations(self):
        self.work_stations.all().delete()


class StationFixedPriceRule(BaseModel):
    station = models.ForeignKey(Station, verbose_name=_("station"), related_name="fixed_prices")
    rule_set = models.ForeignKey(RuleSet, verbose_name=_("rule set"))
    city_area_1 = CityAreaField(verbose_name=_("city area 1"), related_name="fixed_price_rules_1")
    city_area_2 = CityAreaField(verbose_name=_("city area 2"), related_name="fixed_price_rules_2")
    price = models.FloatField(_("price"))

    def is_active(self, lat1, lon1, lat2, lon2, day, t):
        contains = (self.city_area_1.contains(lat1, lon1) and self.city_area_2.contains(lat2, lon2)) or \
                   (self.city_area_2.contains(lat1, lon1) and self.city_area_1.contains(lat2, lon2))
        return contains and self.rule_set.is_active(day, t)


class Driver(BaseModel):
    station = models.ForeignKey(Station, verbose_name=_("station"), related_name="drivers")
    name = models.CharField(_("name"), max_length=140, null=True, blank=True)
    phone = models.CharField(_("phone number"), max_length=15)
    is_active = models.BooleanField(_('active'), default=True)

    dn_station_name = models.CharField(_("station name"), max_length=50)

    def save(self, *args, **kwargs):
        if self.station:
            self.dn_station_name = self.station.name

        super(Driver, self).save(*args, **kwargs)

    def get_taxis(self, only_active=True):
        taxis = [r.taxi for r in TaxiDriverRelation.objects.filter(driver=self)]
        if only_active:
            taxis = filter(lambda taxi: taxi.is_active, taxis)

        return sorted(taxis, key=lambda taxi: taxi.number)

    def serialize_for_ws(self, queried_taxis=None):
        taxis = queried_taxis or Taxi.objects.filter(station=self.station, is_active=True).order_by("number")
        self_taxis = self.get_taxis()
        return {'id': self.id,
                'name': self.name,
                'phone': self.phone,
                'taxis': [{'id': taxi.id, 'number': taxi.number} for taxi in self_taxis],
                'available_taxis': sorted([{'id': t.id, 'number': t.number} for t in set(taxis) - set(self_taxis)], key=lambda x: x['number'])}

    def __unicode__(self):
        return u"%s" % (self.name)

class Taxi(BaseModel):
    station = models.ForeignKey(Station, verbose_name=_("station"), related_name="taxis")
    number = models.IntegerField(_("taxi_number"), max_length=10)
    is_active = models.BooleanField(_('active'), default=True)

    dn_station_name = models.CharField(_("station name"), max_length=50)

    def save(self, *args, **kwargs):
        if self.station:
            self.dn_station_name = self.station.name

        super(Taxi, self).save(*args, **kwargs)

    def get_drivers(self, only_active=True):
        drivers = [r.driver for r in TaxiDriverRelation.objects.filter(taxi=self)]
        if only_active:
            drivers = filter(lambda driver: driver.is_active, drivers)

        return sorted(drivers, key=lambda driver: driver.name)

    def serialize_for_ws(self, queried_drivers=None):
        drivers = queried_drivers or Driver.objects.filter(station=self.station, is_active=True).order_by("name")
        self_drivers = self.get_drivers()
        return {'id': self.id,
                'number': self.number,
                'drivers': [{'id': driver.id, 'name': driver.name, 'phone': driver.phone} for driver in self_drivers],
                'available_drivers': sorted([{'id': d.id, 'name': d.name} for d in set(drivers) - set(self_drivers)], key=lambda x: x['name'])}

    def __unicode__(self):
        return u"%s" % (self.number)

class TaxiDriverRelation(BaseModel):
    driver = models.ForeignKey(Driver, verbose_name=_("driver"))
    taxi = models.ForeignKey(Taxi, verbose_name=_("taxi"))

    dn_station_name = models.CharField(_("station name"), max_length=50)

    def save(self, *args, **kwargs):
        self.dn_station_name = self.driver.dn_station_name

        super(TaxiDriverRelation, self).save(*args, **kwargs)


    class Meta:
        unique_together = ("driver", "taxi")

    def clean(self):
        if self.taxi.station != self.driver.station:
            raise ValidationError("Driver and Taxi must belong to the same station")


class RideComputationSet(BaseModel):
    name = models.CharField(_("name"), max_length=50)

    @property
    def orders(self):
        computations = self.members.filter(status=RideComputationStatus.COMPLETED)
        computation = filter(lambda c: c.orders.count(), computations)[0]
        return computation.orders.all()


class RideComputation(BaseModel):
    set = models.ForeignKey(RideComputationSet, verbose_name=_("Computation set"), related_name="members", null=True, blank=True)
    key = models.CharField(max_length=150, null=True, blank=True, editable=False)
    algo_key = models.CharField(max_length=150, null=True, blank=True, editable=False)

    debug = models.BooleanField(default=False, editable=False)
    status = StatusField(_("status"), choices=RideComputationStatus.choices(), default=RideComputationStatus.PENDING)

    hotspot_depart_time = UTCDateTimeField(null=True, blank=True, editable=False)
    hotspot_arrive_time = UTCDateTimeField(null=True, blank=True, editable=False)

    toleration_factor = models.FloatField(null=True, blank=True)
    toleration_factor_minutes = models.FloatField(null=True, blank=True)
    statistics = models.TextField(null=True, blank=True)

    def change_status(self, old_status=None, new_status=None, safe=True):
        return self._change_attr_in_transaction("status", old_value=old_status, new_value=new_status, safe=safe)

class SharedRide(BaseModel):

    depart_time = UTCDateTimeField(_("depart time"))
    arrive_time = UTCDateTimeField(_("arrive time"))

    status = StatusField(_("status"), choices=SHARED_RIDE_STATUS, default=PENDING)
    computation = models.ForeignKey(RideComputation, verbose_name=_("computation"), related_name="rides", null=True, blank=True)

    station = models.ForeignKey(Station, verbose_name=_("station"), related_name="rides", null=True, blank=True)
    driver = models.ForeignKey(Driver, verbose_name=_("assigned driver"), related_name="rides", null=True, blank=True)
    taxi = models.ForeignKey(Taxi, verbose_name=_("assigned taxi"), related_name="rides", null=True, blank=True)

    debug = models.BooleanField(default=False, editable=False)

    sent_time = UTCDateTimeField("sent time", null=True, blank=True)
    received_time = UTCDateTimeField("received time", null=True, blank=True)

    _value = models.FloatField(null=True, blank=True, editable=False) # the value of this ride to the assigned station
    _stops = models.IntegerField(null=True, blank=True, editable=False)

    @property
    def value(self):
        if not self._value and self.station:
            logging.info("updating value for SharedRide[%s]" % self.id)
            self._value = self.station.get_ride_price(self)
            self.save()

        return self._value

    @property
    def first_pickup(self):
        pickups =  self.points.filter(type=StopType.PICKUP).order_by("stop_time")
        if pickups:
            return pickups[0]
        else:
            return None

    @property
    def last_dropoff(self):
        dropoffs =  self.points.filter(type=StopType.DROPOFF).order_by("-stop_time")
        if dropoffs:
            return dropoffs[0]
        else:
            return None

    @property
    def stops(self):
        """
        Compute the number of stops not counting the first one (starting point of the ride).
        @return: number of stops
        """
        if not self._stops:
            logging.info("updating stops for SharedRide[%s]" % self.id)
            self._stops = len(set([(p.lat, p.lon) for p in self.points.all()])) - 1 # don't count the starting point
            self.save()

        return self._stops

    @property
    def charged_stops(self):
        return self.stops - 1

    def get_log(self):
        orders = list(self.orders.all())
        return u"""

    ride.id: %s
    ride.debug: %s

    station: %s

    depart_time: %s

    orders:
    %s

    passengers:
    %s
    """ % (self.id,
           self.debug,
           self.station,
           self.depart_time,
           "\n".join([unicode(order) for order in orders]),
           "\n".join([unicode(order.passenger) for order in orders]))

    def serialize_for_ws(self):
        return {'pickups': [ { 'num_passengers': p.pickup_orders.count(),
                               'passenger_phones': [order.passenger.phone for order in p.pickup_orders.all()],
                               'address': p.address,
                               'time': p.stop_time.strftime("%H:%M") } for p in self.points.filter(type=StopType.PICKUP).order_by("stop_time")],
                'dropoffs': [ { 'num_passengers' : p.dropoff_orders.count(),
                                'address': p.address,
                                'passenger_phones': [order.passenger.phone for order in p.dropoff_orders.all()],
                                'time': p.stop_time.strftime("%H:%M") } for p in self.points.filter(type=StopType.DROPOFF).order_by("stop_time")],
                'depart_time': to_js_date(self.depart_time),
                'arrive_time': to_js_date(self.arrive_time),
                'id': self.id,
                'status': self.status,
                'driver': {'name': self.driver.name, 'id': self.driver.id} if self.driver else "",
                'taxi': {'number': self.taxi.number, 'id': self.taxi.id} if self.taxi else "",
                'value': self.value or "",
                'debug': self.debug,
                'driver_jist': self.driver_jist()
        }
    def serialize_for_fax(self):
        return {
            "names"             : ", ".join([order.passenger.user.first_name for order in self.orders.all()]),
            "pickup_address"    : self.first_pickup.address,
            "timeout"           : (self.depart_time - RIDE_SENTINEL_GRACE - utc_now()).seconds,
            "id"                : self.id
        }
    def change_status(self, old_status=None, new_status=None):
        if self._change_attr_in_transaction("status", old_status, new_status):
            sig_args = {
                'sender': 'sharedride_status_changed_signal',
                'obj': self,
                'status': new_status
            }
            ride_status_changed_signal.send(**sig_args)
        else:
            raise UpdateStatusError("update shared ride status failed: %s to %s" % (old_status, new_status))

    def get_status_label(self):
        for key, label in SHARED_RIDE_STATUS:
            if key == self.status:
                return label

        raise ValueError("invalid status")

    def driver_jist(self):
        ws_lang_code = settings.LANGUAGES[self.station.language][0]
        current_lang = translation.get_language()
        translation.activate(ws_lang_code)

        t = get_template("driver_notification_msg.html")

        pickups = []
        for p in self.points.filter(type=StopType.PICKUP).order_by("stop_time"):
            pickups.append("%s %s" % (p.clean_address, p.pickup_orders.all()[0].passenger.phone) if p.pickup_orders.count() == 1 else p.clean_address)

        dropoffs = []
        for p in self.points.filter(type=StopType.DROPOFF).order_by("stop_time"):
            dropoffs.append("%s %s" % (p.clean_address, p.dropoff_orders.all()[0].passenger.phone) if p.dropoff_orders.count() == 1 else p.clean_address)

        template_data = {
            'first_pickup_time': self.first_pickup.stop_time.strftime("%H:%M"),
            'pickups': ", ".join(pickups),
            'dropoffs': ", ".join(dropoffs)
        }
        msg = t.render(Context(template_data))

        translation.activate(current_lang)

        return msg.replace("\n","").replace("'","")


class RidePoint(BaseModel):
    ride = models.ForeignKey(SharedRide, verbose_name=_("ride"), related_name="points", null=True, blank=True)

    stop_time = UTCDateTimeField(_("stop time"))
    type = models.IntegerField(_("type"), choices=StopType.choices(), default=0)

    lon = models.FloatField(_("longtitude"))
    lat = models.FloatField(_("latitude"))
    address = models.CharField(_("address"), max_length=200, null=True, blank=True)

    def __unicode__(self):
        return u"RidePoint [%d]" % self.id

    @property
    def clean_address(self):
        return re.sub(",?\s+תל אביב יפו".decode("utf-8"), "", self.address)

class Passenger(BaseModel):
    user = models.OneToOneField(User, verbose_name=_("user"), related_name="passenger", null=True, blank=True)

    country = models.ForeignKey(Country, verbose_name=_("country"), related_name="passengers")
    default_station = models.ForeignKey(Station, verbose_name=_("Default station"), related_name="default_passengers", default=None, null=True, blank=True)
    default_sharing_station = models.ForeignKey(Station, verbose_name=_("Default sharing station"), default=None, null=True, blank=True)
    originating_station = models.ForeignKey(Station, verbose_name=(_("originating station")), related_name="originated_passengers", null=True, blank=True, default=None)

    phone = models.CharField(_("phone number"), max_length=15)
    phone_verified = models.BooleanField(_("phone verified"))

    accept_mailing = models.BooleanField(_("accept mailing"), default=True)

    # used to login anonymous passengers
    login_token = models.CharField(_("login token"), max_length=40, null=True, blank=True)

    session_keys = ListField(models.CharField(max_length=32)) # session is identified by a 32-character hash

    # disallow ordering
    is_banned = models.BooleanField(_("banned"), default=False)

    invoice_id = models.IntegerField(_("invoice id"), null=True, blank=True, unique=True, editable=False)

    @property
    def name(self):
        try:
            if self.user:
                name = self.user.first_name or self.user.get_full_name() or self.user.username
                return name
        except User.DoesNotExist:
            pass

        return UNKNOWN_USER

    @property
    def full_name(self):
        try:
            if self.user:
                name = self.user.get_full_name() or self.user.username
                return name
        except User.DoesNotExist:
            pass

        return UNKNOWN_USER

    def _get_business(self):
        try:
            return self._business
        except Business.DoesNotExist:
            return None

    def _set_business(self, value):
        self._business = value

    business = property(_get_business, _set_business)

    def cleanup_session_keys(self):
        db_sessions_qs = Session.objects.filter(session_key__in=self.session_keys).filter(
            expire_date__gt=datetime.datetime.now())
        db_session_keys = [s.session_key for s in db_sessions_qs]

        for session_key in self.session_keys:
            if session_key not in db_session_keys:
                self.session_keys.remove(session_key)
        self.save()

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
        # try to get the passenger of the authenticated user
        passenger = get_model_from_request(cls, request)

        # try to get passenger from the session
        if not passenger:
            passenger = request.session.get(CURRENT_PASSENGER_KEY, None)
            if passenger: passenger = passenger.fresh_copy() # refresh the passenger copy stored in the session

        # try to get passenger from passed token
        if not passenger:
            token = request.POST.get(PASSENGER_TOKEN, None) or request.GET.get(PASSENGER_TOKEN)
            if token:
                try:
                    passenger = cls.objects.get(login_token=token)
                    if passenger.user: # authenticate this passenger also using a session cookie
                        if not hasattr(passenger.user, "backend"):
                            passenger.user.backend = 'django.contrib.auth.backends.ModelBackend'
                        login(request, passenger.user)
                except cls.DoesNotExist:
                    pass
        return passenger


    def __unicode__(self):
        return u"Passenger: %s, %s" % (self.phone, self.name)

class Business(BaseModel):
    passenger = models.OneToOneField(Passenger, verbose_name=_("passenger"), related_name="_business")

    name = models.CharField(_("business name"), max_length=50)
    contact_person = models.CharField(_("contact person"), max_length=50)

    # holds the full address
    address = models.CharField(_("address"), max_length=80)

    city = models.ForeignKey(City, verbose_name=_("city"), related_name="businesses")
    street_address = models.CharField(_("address"), max_length=80)
    house_number = models.IntegerField(_("house_number"), max_length=10)
    lon = models.FloatField(_("longtitude"))
    lat = models.FloatField(_("latitude"))

    confine_orders = models.BooleanField(_("confine orders"), default=False)

    from_station = models.ForeignKey(Station, default=None, null=True, blank=True)

    def send_welcome_email(self, chosen_password):
        # note: email is sent in Hebrew
        current_lang = translation.get_language()
        translation.activate(settings.LANGUAGE_CODE)

        subject = ugettext("business welcome mail subject")
        link = self.from_station.get_station_page_link() if self.from_station else "http://www.WAYbetter.com"
        pretty_link = link.replace('http://','')
        template_args = {'name': self.name, 'password': chosen_password, 'link': link, 'pretty_link': pretty_link}
        t = get_template("business_welcome_email.html")

        send_mail_as_noreply(self.passenger.user.email, subject, html=t.render(Context(template_args)))

        # send us a copy of the mail
        template_args["show_include_text"] = True
        notify_by_email("New business joined", html=t.render(Context(template_args)))

        translation.activate(current_lang)

def post_delete_business(sender, instance, **kwargs):
    passenger = instance.passenger
    user = passenger.user
    user.is_active = False
    user.save()

models.signals.post_delete.connect(post_delete_business, sender=Business)

class Phone(BaseModel):
    local_phone = models.CharField(_("phone number"), max_length=20, validators=[phone_validator])

    station = models.ForeignKey(Station, verbose_name=_("station"), related_name="phones", null=True, blank=True)


    def __unicode__(self):
        if self.local_phone:
            return u"%s" % self.local_phone
        else:
            return u""


class WorkStation(BaseModel):

    def __init__(self, *args, **kwargs):
        super(WorkStation, self).__init__(*args, **kwargs)
        self._is_online_old = self.is_online

    user = models.OneToOneField(User, verbose_name=_("user"), related_name="work_station")

    station = models.ForeignKey(Station, verbose_name=_("station"), related_name="work_stations")
    token = models.CharField(_("token"), max_length=50, null=True, blank=True)
    installer_url = models.URLField(_("installer URL"), max_length=500, null=True, blank=True)
    was_installed = models.BooleanField(_("was installed"), default=False)
    accept_orders = models.BooleanField(_("Accept orders"), default=True)
    accept_unconfined_orders = models.BooleanField(default=True, help_text="Accept orders not confined to a station e.g., booked from PickMeApp")
    accept_shared_rides = models.BooleanField(_("Accept Shared Rides"), default=False)
    accept_debug = models.BooleanField(_("Accept debug"), default=False)

    last_assignment_date = UTCDateTimeField(_("last order date"), null=True, blank=True,
                                            default=datetime.datetime(1, 1, 1))

    channel_id = models.CharField(_("channel_id"), max_length=50, null=True, blank=True)
    is_online = models.BooleanField(_("is online"), default=False)

    # denormalized fields
    dn_station_id = models.IntegerField(_("station id"), null=True, blank=True)
    dn_station_name = models.CharField(_("station name"), max_length=50, null=True, blank=True)

    def generate_new_channel_id(self):
        """
        create a new channel_id for this WorkStation

        @return: the new channel_id
        """
        self.channel_id = get_channel_key(self)
        self.is_online = False # a signal will turn it back on
        self.save()
        return self.channel_id

    def save(self, *args, **kwargs):
        if self.station:
            self.dn_station_id  = self.station.id
            self.dn_station_name = self.station.name

        super(WorkStation, self).save(*args, **kwargs)

        # emit online/offline signals
        if self._is_online_old != self.is_online:
            self._is_online_old = self.is_online
            if self.is_online:
                workstation_online_signal.send(sender="workstation_connected", obj=self)
            else:
                workstation_offline_signal.send(sender="workstation_disconnected", obj=self)


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
        build_installer_for_workstation(instance=self, url="build_installer")

    def build_sharing_installer(self):
        """
        Invokes the build_installer_url service in the AIR build service,
        providing it the workstation token.
        """
        build_installer_for_workstation(instance=self, url="build_sharing_installer")


def build_installer_for_workstation(instance, url):
    if instance.token is None or len(instance.token) == 0:
        instance.token = generate_random_token(alpha_or_digit_only=True)
    if instance.installer_url is None or len(instance.installer_url) == 0:
        try:
            url = "%s%s/" % (settings.BUILD_SERVICE_BASE_URL, url)
            data = {"token": instance.token, "workstation_id": instance.id}
            params = urllib.urlencode(data)
            installer_url = urllib2.urlopen(url, params).read()
            instance.installer_url = installer_url
            instance.save()
        except:
            time.sleep(5)
            url = "%sget_installer/?token=%s" % (settings.BUILD_SERVICE_BASE_URL, instance.token)
            installer_url = urllib2.urlopen(url).read()
            instance.installer_url = installer_url
            instance.save()

    return instance.installer_url

#TODO_WB: what is that needed for:
#models.signals.post_save.connect(build_installer_for_workstation, sender=WorkStation)

RATING_CHOICES = ((0, ugettext("Unrated")),
                  (1, ugettext("Very poor")),
                  (2, ugettext("Not so bad")),
                  (3, ugettext("Average")),
                  (4, ugettext("Good")),
                  (5, ugettext("Perfect")))

class Device(BaseModel):
    """
    A Device: identified by a udid (generated using uniqueIdentifier)
    """
    udid = models.CharField(_("udid"), max_length=64)
    gudid = models.CharField(_("gudid"), max_length=64, null=True, blank=True)

    origin = models.CharField(_("origin"), max_length=64, default="organic")

    @classmethod
    def by_udid(cls, udid):
        return obj_by_attr(cls, "udid", udid)

    def __unicode__(self):
        return u"[%d] %s" % (self.id or 0, self.udid)

class InstalledApp(BaseModel):
    """
    An application on a specific device. The app_udid is unique for a device and bundle ID
    """
    app_udid = models.CharField(_("app udid"), max_length=64)
    name = models.CharField(_("name"), max_length=100)
    user_agent = models.CharField(_("user agent"), max_length=250, null=True, blank=True)

    blocked = models.BooleanField(_("blocked"), default=False)

    install_count = models.IntegerField(_("install count"), default=1)

    passenger = models.ForeignKey(Passenger, verbose_name=_("passenger"), related_name="installed_apps", null=True, blank=True)
    device = models.ForeignKey(Device, verbose_name=_("device"), related_name="installed_apps", null=True, blank=True)

    @classmethod
    def by_app_udid(cls, app_udid):
        return obj_by_attr(cls, "app_udid", app_udid)

    def __unicode__(self):
        return u"[%d] %s" % (self.id or 0, self.app_udid)



class Order(BaseModel):
    passenger = models.ForeignKey(Passenger, verbose_name=_("passenger"), related_name="orders", null=True, blank=True)
    station = models.ForeignKey(Station, verbose_name=_("station"), related_name="orders", null=True, blank=True)
    originating_station = models.ForeignKey(Station, verbose_name=(_("originating station")),
                                            related_name="originated_orders", null=True, blank=True, default=None)
    confining_station = models.ForeignKey(Station, verbose_name=(_("confining station")),
                                            related_name="confined_orders", null=True, blank=True, default=None)

    debug = models.BooleanField(default=False, editable=False)
    mobile = models.BooleanField(_("mobile"), default=False)
    user_agent = models.CharField(_("user agent"), max_length=250, null=True, blank=True, default=False)

    status = StatusField(_("status"), choices=ORDER_STATUS, default=PENDING)
    language_code = models.CharField(_("order language"), max_length=5, default=settings.LANGUAGE_CODE)

    from_country = models.ForeignKey(Country, verbose_name=_("from country"), related_name="orders_from")
    from_city = models.ForeignKey(City, verbose_name=_("from city"), related_name="orders_from")
    from_city_area = models.ForeignKey(CityArea, verbose_name=_("from city area"), related_name="orders_from", null=True
                                       , blank=True)
    from_postal_code = models.CharField(_("from postal code"), max_length=10, null=True, blank=True)
    from_street_address = models.CharField(_("from street address"), max_length=50)
    from_house_number = models.IntegerField(_("from_house_number"), max_length=10, null=True,
                                            blank=True) # TODO_WB: make this mandatory in a safe manner

    from_geohash = models.CharField(_("from goehash"), max_length=13)
    from_lon = models.FloatField(_("from_lon"))
    from_lat = models.FloatField(_("from_lat"))
    # this field holds the data as typed by the user
    from_raw = models.CharField(_("from address"), max_length=50)

    to_country = models.ForeignKey(Country, verbose_name=_("to country"), related_name="orders_to", null=True,
                                   blank=True)
    to_city = models.ForeignKey(City, verbose_name=_("to city"), related_name="orders_to", null=True, blank=True)
    to_city_area = models.ForeignKey(CityArea, verbose_name=_("to city area"), related_name="orders_to", null=True,
                                     blank=True)
    to_postal_code = models.CharField(_("to postal code"), max_length=10, null=True, blank=True)
    to_street_address = models.CharField(_("to street address"), max_length=50, null=True, blank=True)
    to_house_number = models.IntegerField(_("to_house_number"), max_length=10, null=True, blank=True)

    to_geohash = models.CharField(_("to goehash"), max_length=13, null=True, blank=True)
    to_lon = models.FloatField(_("to_lon"), null=True, blank=True)
    to_lat = models.FloatField(_("to_lat"), null=True, blank=True)
    # this field holds the data as typed by the user
    to_raw = models.CharField(_("to address"), max_length=50, null=True, blank=True)

    type = models.IntegerField(choices=OrderType.choices(), default=OrderType.PICKMEAPP)

    installed_app = models.ForeignKey(InstalledApp, verbose_name=_("installed_app"), related_name="orders", null=True,
                                      blank=True)

    # pickmeapp fields
    pickup_time = models.IntegerField(_("pickup time"), null=True, blank=True)
    future_pickup = models.BooleanField(_("future pickup"), default=False)
    taxi_is_for = models.CharField(max_length=128, null=True, blank=True, default="")
    comments = models.CharField(max_length=128, null=True, blank=True, default="")

    # sharing fields
    ride = models.ForeignKey(SharedRide, verbose_name=_("ride"), related_name="orders", null=True, blank=True)
    computation = models.ForeignKey(RideComputation, related_name="orders", null=True, blank=True)
    pickup_point = models.ForeignKey(RidePoint, verbose_name=_("pickup point"), related_name="pickup_orders", null=True, blank=True)
    dropoff_point = models.ForeignKey(RidePoint, verbose_name=_("dropoff point"), related_name="dropoff_orders", null=True, blank=True)
    depart_time = UTCDateTimeField(_("depart time"), null=True, blank=True)
    arrive_time = UTCDateTimeField(_("arrive time"), null=True, blank=True)
    price = models.FloatField(null=True, blank=True, editable=False)
    num_seats = models.PositiveIntegerField(default=1)

    # ratings
    passenger_rating = models.IntegerField(_("passenger rating"), choices=RATING_CHOICES, null=True, blank=True)

    # denormalized fields
    station_name = models.CharField(_("station name"), max_length=50, null=True, blank=True)
    station_id = models.IntegerField(_("station id"), null=True, blank=True)
    passenger_phone = models.CharField(_("passenger phone"), max_length=50, null=True, blank=True)
    passenger_id = models.IntegerField(_("passenger id"), null=True, blank=True)

    api_user = models.ForeignKey(APIUser, verbose_name=_("api user"), related_name="orders", null=True, blank=True)

    @property
    def invoice_description(self):
        if self.type == OrderType.PRIVATE:
            type = _("private")
        else:
            type = _("shared")

        return _('%(date)s: Taxi ride from %(pickup)s to %(dropoff)s %(seats)s') % {
            "pickup"    : self.from_raw,
            "dropoff"   : self.to_raw,
            "date"      : format_dt(self.depart_time),
            "seats"     : "(%s %s)" % (self.num_seats, ugettext("seats")) if self.num_seats > 1 else ""
        }

    def save(self, *args, **kwargs):
        if not is_in_transaction():
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

    def change_status(self, old_status=None, new_status=None):
        """
        1. update status in transaction,
        2. send signal if update was successful,
        3. notify when needed
        """
        success = self._change_attr_in_transaction("status", old_status, new_status)
        if success:
            sig_args = {
                'sender': 'order_status_changed_signal',
                'obj': self,
                'status': new_status
            }
            order_status_changed_signal.send(**sig_args)

            if new_status in [TIMED_OUT, FAILED, ERROR]:
                self.notify()

            return success

        else:
            raise UpdateStatusError("update order status failed: %s to %s" % (old_status, new_status))

    def get_pickup_time(self):
        """
        This is used for pickmeapp
        Return the time remaingin until pickup (in seconds), or -1 if pickup time passed already
        """
        if self.future_pickup:
            return ((self.modify_date + datetime.timedelta(minutes=self.pickup_time)) - utc_now()).seconds
        else:
            return -1

    def get_pickup_str(self):
        if self.pickup_point:
            pickup_str = self.pickup_point.stop_time.strftime("%d/%m/%y, %H:%M")

        elif self.computation.hotspot_arrive_time: # to Hotspot, pickup time is estimated
            ride_duration_sec = (self.arrive_time - self.depart_time).seconds
            sharing_dprt = self.arrive_time - datetime.timedelta(seconds=ride_duration_sec * SHARING_TIME_FACTOR)

            d = _("Today") if self.depart_time.date() == default_tz_now().date() else self.depart_time.strftime("%d/%m/%Y")
            pickup_str = u"%s, %s-%s" % (d, sharing_dprt.strftime("%H:%M"), self.depart_time.strftime("%H:%M"))

        else: # from hotspot
            pickup_str = format_dt(self.depart_time)

        return pickup_str
    
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
    Passenger:      %s
    Created:        %s
    From:           %s
    To:             %s
    User Agent:     %s
    """ % (
        self.id, unicode(self.passenger), self.create_date.ctime(), self.from_raw, self.to_raw, self.user_agent)

        if self.originating_station:
            msg += u"""
    From Station:   %s""" % self.originating_station.name

        if self.status == ACCEPTED:
            msg += u"""
    Station:        %s
    Pickup in:      %d minutes""" % (self.station.name, self.pickup_time)

        if self.mobile:
            msg += u"""

    * Ordered from a mobile device."""

        if self.passenger.orders.count() == 1:
            msg += u"""

    * This is a new passenger."""

        if self.passenger.business:
            msg += u"""

    * This is a business passenger: %s.""" % self.passenger.business.name

        if self.assignments.count():
            msg += u"\n\nEvents:"
            for assignment in self.assignments.all().order_by('create_date'):
                msg += u"\n%s: %s [ws: %d] - %s" % (
                assignment.modify_date.ctime(), assignment.station.name, assignment.work_station.id, assignment.get_status_label().upper())

        notify_by_email(subject, msg)

    def serialize_for_sharing(self):
        return { "from_address": self.from_raw,
                 "from_lat": self.from_lat,
                 "from_lon": self.from_lon,
                 "id": self.id,
                 "order_time": time.mktime(self.create_date.timetuple()),
                 "passenger_id": self.passenger_id,
                 "to_address": self.to_raw,
                 "to_lat": self.to_lat,
                 "to_lon": self.to_lon,
                 "num_seats": self.num_seats}

    def serialize_for_myrides(self):
        return {'id': self.id, 'type': self.type, 'from': self.from_raw, 'to': self.to_raw, 'num_seats': self.num_seats,
                'when': self.get_pickup_str(), 'price': self.price}

class OrderAssignment(BaseModel):
    order = models.ForeignKey(Order, verbose_name=_("order"), related_name="assignments")
    work_station = models.ForeignKey(WorkStation, verbose_name=_("work station"), related_name="assignments")
    station = models.ForeignKey(Station, verbose_name=_("station"), related_name="assignments")

    status = StatusField(_("status"), choices=ASSIGNMENT_STATUS, default=PENDING)

    show_date = UTCDateTimeField(_("show date"), auto_now_add=False, null=True, blank=True)

    pickup_address_in_ws_lang = models.CharField(_("pickup_address_in_ws_lang"), max_length=50)
    dropoff_address_in_ws_lang = models.CharField(_("dropoff_address_in_ws_lang"), max_length=50)

    # de-normalized fields
    dn_business_name = models.CharField(_("business name"), max_length=50, null=True, blank=True)
    dn_from_raw = models.CharField(_("from address"), max_length=50, null=True, blank=True)
    dn_to_raw = models.CharField(_("to address"), max_length=50, null=True, blank=True)

    def save(self, *args, **kwargs):
        if not is_in_transaction():
            if self.order:
                if self.order.from_raw:
                    self.dn_from_raw = self.order.from_raw
                if self.order.to_raw:
                    self.dn_to_raw = self.order.to_raw
            if self.order.passenger.business:
                self.dn_business_name = self.order.passenger.business.name

        super(OrderAssignment, self).save(*args, **kwargs)
    @classmethod
    def serialize_for_workstation(cls, queryset_or_order_assignment, base_time=None):
        if isinstance(queryset_or_order_assignment, QuerySet):
            order_assignments = queryset_or_order_assignment
        elif isinstance(queryset_or_order_assignment, cls):
            order_assignments = [queryset_or_order_assignment]
        else:
            raise RuntimeError("Argument must be either QuerySet or %s" % cls.__name__)

        result = []
        for order_assignment in order_assignments:
            if not base_time:
                base_time = order_assignment.create_date

            oa_data = {"pk": order_assignment.order.id, "status": order_assignment.status,
                       "from_raw": order_assignment.pickup_address_in_ws_lang or order_assignment.dn_from_raw,
                       "to_raw": order_assignment.dropoff_address_in_ws_lang or order_assignment.dn_to_raw,
                       "seconds_passed": (utc_now() - base_time).seconds,
                       "current_rating": order_assignment.station.average_rating,
                       "passenger_phone": order_assignment.order.passenger_phone

            }

            if order_assignment.dn_business_name: # assigning a business order
                order = order_assignment.order
                oa_data.update({
                    "business": order_assignment.dn_business_name,
                    'taxi_is_for': order.taxi_is_for,
                    'comments': order.comments
                })

            result.append(oa_data)

        return result

    def get_status_label(self):
        for key, label in ASSIGNMENT_STATUS:
            if key == self.status:
                return label

        raise ValueError("invalid status")

    def change_status(self, old_status=None, new_status=None):
        """
        Change the status of this C{OrderAssignment}

        Update status in transaction, send signal if update was successful

        @param old_status: the old status to check
        @param new_status: the new status to set
        @return: None
        """
        if self._change_attr_in_transaction("status", old_status, new_status):
            sig_args = {
                'sender': 'orderassignment_status_changed_signal',
                'obj': self,
                'status': new_status
            }
            orderassignment_status_changed_signal.send(**sig_args)
        else:
            raise UpdateStatusError("update order assignment status failed: %s to %s" % (old_status, new_status))

    def is_stale(self):
        return (utc_now() - self.create_date).seconds > ORDER_ASSIGNMENT_TIMEOUT

    def __unicode__(self):
        order_id = "<Unknown>"
        if self.order:
            order_id = u"<%d>" % self.order.id

        return u"%s %s %s %s" % (ugettext("order"), order_id, ugettext("assigned to station:"), self.station)


VEHICLE_TYPE_CHOICES = ((1, _("Standard cab")),)

# time and distance dependent rules (meter)
class MeteredRateRule(BaseModel):
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

    def __unicode__(self):
        return self.rule_name

# rules with flat rate (e.g., from city to another city or airport)
class FlatRateRule(BaseModel):
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

    def __unicode__(self):
        return "from %s to %s" % (self.city1.name, self.city2.name)

# rules for extra charges (e.g., phone order)
class ExtraChargeRule(BaseModel):
    rule_name = models.CharField(_("name"), max_length=500)
    is_active = models.BooleanField(_("is active"), default=True)
    country = models.ForeignKey(Country, verbose_name=_("country"), related_name="extra_charge_rules")

    cost = models.FloatField(_("fixed cost"))

    def __unicode__(self):
        return self.rule_name

FEEDBACK_CATEGORIES = ["Website", "Booking", "Registration", "Taxi Ride", "Other"]
FEEDBACK_CATEGORIES_NAMES = [_("Website"), _("Booking"), _("Registration"), _("Taxi Ride"), _("Other")]
FEEDBACK_TYPES = ["Positive", "Negative"]

class Feedback(BaseModel):
    passenger = models.ForeignKey(Passenger, verbose_name=_("passenger"), related_name="feedbacks", null=True,
                                  blank=True)

    def __unicode__(self):
        result = u""
        for f in Feedback.field_names():
            if getattr(self, f):
                msg = getattr(self, f + "_msg")
                result += "<p>%s %s</p>" % (f, u": " + msg if msg else "")

        return result if result else u"Empty Feedback"

    @staticmethod
    def field_names():
        field_names = []
        for category in FEEDBACK_CATEGORIES:
            for type in FEEDBACK_TYPES:
                field_names.append("%s_%s" % (type.lower(), category.lower().replace(" ", "_")))

        return field_names

for i, category in zip(range(len(FEEDBACK_CATEGORIES)), FEEDBACK_CATEGORIES):
    for type in FEEDBACK_TYPES:
        models.CharField(FEEDBACK_CATEGORIES_NAMES[i], max_length=100, null=True, blank=True).contribute_to_class(
            Feedback, "%s_%s_msg" % (type.lower(), category.lower().replace(" ", "_")))
        models.BooleanField(default=False).contribute_to_class(Feedback, "%s_%s" % (
        type.lower(), category.lower().replace(" ", "_")))

# TODO_WB: check if created arg has been fixed and reports False on second save of instance
#def order_init_handler(sender, **kwargs):
#    if kwargs.get("instance").id:
#        order_created_signal.send(sender=Order, obj=kwargs["instance"])
#post_save.connect(receiver=order_init_handler, sender=Order)
#
#def orderassignment_init_handler(sender, **kwargs):
#    if kwargs.get("created"):
#        orderassignment_created_signal.send(sender=OrderAssignment, obj=kwargs["instance"])
#post_save.connect(receiver=orderassignment_init_handler, sender=OrderAssignment)

