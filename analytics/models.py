from django.conf import settings
from common.tz_support import UTCDateTimeField
from django.db import models
from django.utils.translation import ugettext_lazy as _

from ordering.models import Order, WorkStation, Station, OrderAssignment, Passenger, SharedRide
from common.util import EventType, Enum
from common.models import Country, City, BaseModel
from pricing.models import DiscountRule


class BIEventType(Enum):
    APP_INSTALL             = 1
    BOOKING_START           = 2
    BILLING_INFO_COMPLETE   = 3
    REGISTRATION_START      = 4

class AnalyticsEvent(BaseModel):
    type = models.IntegerField(_("type"), choices=EventType.choices())

    order = models.ForeignKey(Order, verbose_name=_("order"), related_name="events", null=True, blank=True)
    order_assignment = models.ForeignKey(OrderAssignment, verbose_name=_("order assignment"), related_name="events", null=True, blank=True)
    work_station = models.ForeignKey(WorkStation, verbose_name=_("work station"), related_name="events", null=True, blank=True)
    station = models.ForeignKey(Station, verbose_name=_("station"), related_name="events", null=True, blank=True)
    passenger = models.ForeignKey(Passenger, verbose_name=_("passenger"), related_name="events", null=True, blank=True)
    country = models.ForeignKey(Country, verbose_name=_("country"), related_name="events", null=True, blank=True)
    city = models.ForeignKey(City, verbose_name=_("city"), related_name="events", null=True, blank=True)
    rating = models.IntegerField(verbose_name=_("ratings"), null=True, blank=True)

    lat = models.FloatField(verbose_name=("lat"), null=True, blank=True)
    lon = models.FloatField(verbose_name=("lon"), null=True, blank=True)

    def save(self, force_insert=False, force_update=False, using=None):
        self.full_clean() # validates model
        super(AnalyticsEvent, self).save()

    def get_label(self):
        return EventType.get_label(self.type)

    
    def __str__(self):
        return self.get_label()


class SearchRequest(BaseModel):
    # TODO_WB: consider adding fields: num of offers returened, chosen offer
    passenger = models.ForeignKey(Passenger, verbose_name=_("passenger"), related_name="search_requests", null=True, blank=True)

    from_lon = models.FloatField(_("from_lon"))
    from_lat = models.FloatField(_("from_lat"))
    from_address = models.CharField(_("from address"), max_length=50)
    from_city = models.CharField(_("from city"), max_length=50)

    to_lon = models.FloatField(_("to_lon"), null=True, blank=True)
    to_lat = models.FloatField(_("to_lat"), null=True, blank=True)
    to_address = models.CharField(_("to address"), max_length=50, null=True, blank=True)
    to_city = models.CharField(_("to city"), max_length=50, null=True, blank=True)

    num_seats = models.PositiveIntegerField(default=1)

    pickup_dt = UTCDateTimeField("pickup dt", null=True, blank=True)

    mobile = models.BooleanField("mobile", default=False)
    private = models.BooleanField("private", default=False)
    luggage = models.IntegerField("luggage", default=0)
    debug = models.BooleanField("debug", default=False)

    language_code = models.CharField("language_code", max_length=5)
    user_agent = models.CharField("user agent", max_length=250, null=True, blank=True)

    @classmethod
    def fromOrderSettings(cls, order_settings, passenger):
        sr = cls()
        if passenger:
            sr.passenger = passenger

        sr.from_address = order_settings.pickup_address.formatted_address
        sr.from_city = order_settings.pickup_address.city_name
        sr.from_lat = order_settings.pickup_address.lat
        sr.from_lon = order_settings.pickup_address.lng

        sr.to_address = order_settings.dropoff_address.formatted_address
        sr.to_city = order_settings.dropoff_address.city_name
        sr.to_lat = order_settings.dropoff_address.lat
        sr.to_lon = order_settings.dropoff_address.lng

        sr.num_seats = order_settings.num_seats
        sr.pickup_dt = order_settings.pickup_dt

        sr.luggage = order_settings.luggage
        sr.private = order_settings.private
        sr.debug = order_settings.debug
        sr.mobile = order_settings.mobile

        sr.language_code = order_settings.language_code
        sr.user_agent = order_settings.user_agent

        return sr

class RideOffer(BaseModel):
    search_req = models.ForeignKey(SearchRequest, verbose_name=_("search request"), related_name="offers")
    ride_key = models.CharField("ride key", max_length=30, null=True, blank=True)

    order = models.ForeignKey(Order, verbose_name=_("order"), related_name="+", null=True, blank=True)
    discount_rule = models.ForeignKey(DiscountRule, verbose_name=_("discount rule"), related_name="+", null=True, blank=True)
    ride = models.ForeignKey(SharedRide, verbose_name="shared ride", related_name='+', null=True, blank=True)
    pickup_dt = UTCDateTimeField("pickup datetime", null=True, blank=True)
    seats_left = models.IntegerField("seats left", null=True, blank=True)
    price = models.FloatField("price", null=True, blank=True)
    new_ride = models.BooleanField("new ride", default=True)

class BIEvent(BaseModel):
    event_type = models.IntegerField("event type", choices=BIEventType.choices())

    passenger = models.ForeignKey(Passenger, verbose_name=_("passenger"), related_name="+", null=True, blank=True)
    order = models.ForeignKey(Order, verbose_name=_("order"), related_name="+", null=True, blank=True)
    mobile = models.BooleanField(_("mobile"), default=False)
    debug = models.BooleanField(_("debug"), default=False)

    lon = models.FloatField(_("lon"), null=True, blank=True)
    lat = models.FloatField(_("lat"), null=True, blank=True)
    user_agent = models.CharField("user agent", max_length=250, null=True, blank=True)

    @staticmethod
    def log(event_type, request=None, **kwargs):
        new_event = BIEvent(event_type=event_type, **kwargs)
        if request:
            new_event.user_agent = request.META.get("HTTP_USER_AGENT")
            new_event.mobile = request.mobile
            new_event.debug = settings.DEV

        new_event.save()
