import re
from common.decorators import order_relative_to_field
from common.tz_support import default_tz_now, to_task_name_safe, ceil_datetime, floor_datetime
from common.util import phone_validator
from django.db import models
from django.utils.translation import ugettext_lazy as _
from common.util import convert_python_weekday, datetimeIterator
from common.models import BaseModel, Country, City, CityAreaField, CityArea
from ordering.models import Passenger, Station
from pricing.models import RuleSet, AbstractTemporalRule
from datetime import datetime, date, timedelta, time
import calendar
import settings

ALGO_COMPUTATION_DELTA = timedelta(minutes=5)
FAX_HANDLING_DELTA = timedelta(minutes=2)
TOTAL_HANDLING_DELTA = ALGO_COMPUTATION_DELTA + FAX_HANDLING_DELTA

ORDERING_ALLOWED_PICKUP_DELTA = TOTAL_HANDLING_DELTA # + hotspot's dispatching time
ORDERING_ALLOWED_DROPOFF_DELTA = timedelta(minutes=60)

PRIVATE_RIDE_HANDLING_FEE = 5 #NIS

PICKUP = "pickup"
DROPOFF = "dropoff"

class HotSpot(BaseModel):
    name = models.CharField(_("hotspot name"), max_length=50)
    description = models.CharField(_("hotspot description"), max_length=100, null=True, blank=True)

    station = models.ForeignKey(Station, related_name="hotspots", null=True, blank=True)
    dispatching_time = models.PositiveIntegerField(verbose_name=_("Dispatching Time"), help_text=_("In minutes"), default=7)
    country = models.ForeignKey(Country, verbose_name=_("country"), related_name="hotspots")
    city = models.ForeignKey(City, verbose_name=_("city"), related_name="hotspots")
    address = models.CharField(_("address"), max_length=80)
    geohash = models.CharField(_("goehash"), max_length=13)
    lon = models.FloatField(_("longtitude"), null=True)
    lat = models.FloatField(_("latitude"), null=True)
    radius = models.FloatField(_("radius"), default=0.7) # radius in which GPS aware devices will decide they are inside this hotspot, in KM
    is_public = models.BooleanField(default=False)

    def get_computation_key(self, hotspot_direction, hotspot_datetime):
        """

        @param hotspot_direction: "from" if the ride starts at hotspot, otherwise "to"
        @param hotspot_datetime: the time and date of the ride
        @return: unique key representing the hotspot at given time and direction. Should match task name expression "^[a-zA-Z0-9_-]{1,500}$"
        """
        return "_".join([str(self.id), hotspot_direction, to_task_name_safe(hotspot_datetime)])

    def get_price(self, lat, lon, day, t):
        """
        @param lat:
        @param lon:
        @param day: date of ride
        @param t: time of ride
        @return: price as float if any price found, otherwise returns None
        """
        #noinspection PyUnresolvedReferences
        for rule_id in self.get_hotspotcustompricerule_order():
            rule = HotSpotCustomPriceRule.by_id(rule_id)

            if rule.is_active(lat, lon, day, t):
                return rule.price

        active_rule_set = RuleSet.get_active_set(day, t)
        if active_rule_set:
            active_tariff_rules = self.tariff_rules.filter(rule_set=active_rule_set)
            for rule in CityArea.relative_sort_models(active_tariff_rules):
                if rule.is_active(lat, lon):
                    return rule.price

        return None

    def get_allowed_ordering_time(self, hotspot_type):
        allowed_time = None
        if hotspot_type == PICKUP:
            allowed_time = default_tz_now() + ORDERING_ALLOWED_PICKUP_DELTA + timedelta(minutes=self.dispatching_time)
        elif hotspot_type == DROPOFF:
            allowed_time = default_tz_now() + ORDERING_ALLOWED_DROPOFF_DELTA

        return allowed_time

    def get_next_active_datetime(self, base_time=None, timeframe=timedelta(weeks=1)):
        """
        Return the next datetime the hotspot is active in given range, or None
        @param base_time: the datetime searching starts at
        @param timeframe: a timedelta within to search
        @return: datetime or None
        """
        if not base_time:
            base_time = default_tz_now()

        d = base_time.date()
        t1 = base_time.time()

        next = None
        times = self.get_times_for_day(day=d, start_time=t1)
        if times:
            next = datetime.combine(d, times[0])
        if not next:
            itr = datetimeIterator(d + timedelta(days=1), d + timeframe)
            for day in itr:
                times = self.get_times_for_day(day=day)
                if times:
                    next = datetime.combine(day, times[0])
                    break

        if next:
            next = next.replace(tzinfo=base_time.tzinfo)

        return next


    def get_times_for_day(self, day=None, start_time=None, end_time=None, offset=0, ceil=False, floor=False):
        """
        Get active times for hotspot on day, within given time frame (if given)
        @param day: datetime.date instance
        @param start_time: datetime.time
        @param end_time: datetime.time
        @param offset: number
        @return: list of datetime.time
        """
        d = day or date.today()

        times = set()
        for rule in self.service_rules.all():
            if rule.is_active(day=d, t=None): # rule is active on day
                times.update(rule.get_times(start_time, end_time, offset))

        times = sorted(times)

        if ceil:
            ceiled_times = []
            for t in times:
                # use datetime to ceil and check it didn't ceil to next day
                dt = ceil_datetime(datetime.combine(d, t))
                if dt.date() == d:
                    ceiled_times.append(dt.time())
            return ceiled_times
        elif floor:
            floored_times = []
            for t in times:
                # use datetime to floor and check it didn't ceil to previous day
                dt = floor_datetime(datetime.combine(d, t))
                if dt.date() == d:
                    floored_times.append(dt.time())
            return floored_times
        else:
            return times

    def get_dates_for_month(self, year, month):
        start_date = date(year, month, 1)
        end_date = date(year, month, calendar.monthrange(year, month)[1]) # last day of month
        return self.get_dates(start_date, end_date)


    def get_dates(self, start_date, end_date):
        """
        Dates on which the hotspot is active
        @param start_date: datetime.date instance
        @param end_date: datetime.date instance
        @return: a list of dates
        """
        weekdays = set()
        dates = set()

        for rule in self.service_rules.all():
            weekdays.update(rule.get_weekdays())
            dates.update(rule.get_dates(start_date, end_date))

        itr = datetimeIterator(start_date, end_date)
        for d in itr:
            if convert_python_weekday(d.weekday()) in weekdays:
                dates.add(d)

        return sorted(list(dates))


    def serialize_for_order(self, address_type):
        # TODO_WB: add house number field to hotspot model
        hn = re.search("(\d+)", self.address)
        hn = hn.groups()[0] if hn else 0

        return {'%s_raw' % address_type: '%s, %s' % (self.address, self.city),
                '%s_street_address' % address_type: self.address.replace(hn, ""),
                '%s_house_number' % address_type: hn,
                '%s_lon' % address_type: self.lon,
                '%s_lat' % address_type: self.lat,
                '%s_geohash' % address_type: self.geohash,
                '%s_city' % address_type: self.city.id,
                '%s_country' % address_type: self.country.id}


class HotSpotServiceRule(AbstractTemporalRule):
    TIME_INTERVAL_CHOICES = [(5, "5 min"), (10, "10 min"), (15, "15 min"), (30, "30 min"), (60, "1 hour")]
    hotspot = models.ForeignKey(HotSpot, verbose_name=_("hotspot"), related_name="service_rules")
    interval = models.IntegerField(_("time interval"), choices=TIME_INTERVAL_CHOICES) # minutes

    def get_times(self, start_time=None, end_time=None, offset=0):
        """
        Times the rule is active on the days it is active.
        @param start_time: a datetime.time lower bound.
        @param end_time: a datetime.time upper bound.
        @param offset: number of seconds to add/remove
        @return: a list of datetimes.
        """
        t1 = start_time or time.min
        t2 = end_time or time.max
        today = date.today()
        
        times = []
        itr = datetimeIterator(datetime.combine(today, self.from_hour), datetime.combine(today, self.to_hour), delta=timedelta(minutes=self.interval))
        for d in itr:
            if datetime.combine(today, t1) <= d <= datetime.combine(today, t2):
                times.append((d + timedelta(seconds=offset)).time())

        return times


class HotSpotCustomPriceRule(AbstractTemporalRule):
    hotspot = models.ForeignKey(HotSpot, verbose_name=_("hotspot"), related_name="custom_rules")
    city_area = CityAreaField(verbose_name=_("city area"))
    price = models.FloatField(_("price"))

    class Meta:
        order_with_respect_to = 'hotspot'

    def is_active(self, lat, lon, day, t):
        # using super does not work for some reason: super(AbstractTemporalRule, self).is_active(day, t)
        return self.city_area.contains(lat, lon) and getattr(AbstractTemporalRule, "is_active")(self, day, t)


class HotSpotTariffRule(BaseModel):
    hotspot = models.ForeignKey(HotSpot, verbose_name=_("hotspot"), related_name="tariff_rules")
    rule_set = models.ForeignKey(RuleSet, verbose_name=_("rule set"))
    city_area = CityAreaField(verbose_name=_("city area"))
    price = models.FloatField(_("price"))

    #    class Meta:
    #        ordering = ["city_area"]

    def is_active(self, lat, lon, day=None, t=None):
        result = self.city_area.contains(lat, lon)
        if day and t:
            result = result and self.rule_set.is_active(day, t)

        return result

order_relative_to_field(HotSpotTariffRule, "rule_set")

class HotSpotTag(BaseModel):
    name = models.CharField(_("tag"), max_length=50)
    hotspot = models.ForeignKey(HotSpot, verbose_name=_("hotspot"), related_name="tags")


class Producer(BaseModel):
    name = models.CharField(_("name"), max_length=50)
    passenger = models.OneToOneField(Passenger, related_name="producer")
    default_sharing_station = models.ForeignKey(Station, verbose_name=_("Default sharing station"), default=None, null=True, blank=True)
    # hotspots ?


class ProducerPassenger(BaseModel):
    producer = models.ForeignKey(Producer, related_name="passengers")
    passenger = models.OneToOneField(Passenger, related_name="producerpassenger", default=None)

    name = models.CharField(_("name"), max_length=50)
    phone = models.CharField(_("phone number"), max_length=15, validators=[phone_validator])
    is_sharing = models.BooleanField(default=True)

    country = models.ForeignKey(Country)
    city = models.ForeignKey(City)
    address = models.CharField(_("address"), max_length=80)
    street_address = models.CharField(_("address"), max_length=80)
    house_number = models.IntegerField(_("house_number"), max_length=10)
    lon = models.FloatField(_("longtitude"))
    lat = models.FloatField(_("latitude"))
    geohash = models.CharField(_("goehash"), max_length=13)

    def save(self, *args, **kargs):
        if not hasattr(self, "country"):
            country = Country.objects.get(code=settings.DEFAULT_COUNTRY_CODE)
            self.country = country
        if hasattr(self, "passenger"):
            self.passenger.phone = self.phone
            self.passenger.save()
        else:
            try:
                passenger = Passenger.objects.get(phone=self.phone)
            except Passenger.DoesNotExist:
                country = Country.objects.get(code=settings.DEFAULT_COUNTRY_CODE)
                passenger = Passenger(phone=self.phone, country=country)
                passenger.save()

            self.passenger = passenger

        super(ProducerPassenger, self).save(*args, **kargs)

    def serialize_for_order(self, address_type):
        return {'%s_raw' % address_type:self.address,
                '%s_street_address' % address_type: self.street_address,
                '%s_house_number' % address_type: self.house_number,
                '%s_lon' % address_type: self.lon,
                '%s_lat' % address_type: self.lat,
                '%s_geohash' % address_type: self.geohash,
                '%s_city' % address_type: self.city.id,
                '%s_country' % address_type: self.country.id}