import logging
import re
import math
from common.decorators import order_relative_to_field
from common.route import calculate_time_and_distance
from common.tz_support import default_tz_now, to_task_name_safe, ceil_datetime, floor_datetime
from common.util import phone_validator
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from common.util import convert_python_weekday, datetimeIterator
from common.models import BaseModel, Country, City, CityAreaField, CityArea
from django.core.validators import MaxValueValidator, MinValueValidator
from ordering.models import Passenger, Station
from ordering.pricing import estimate_cost
from pricing.models import RuleSet, AbstractTemporalRule, PRIVATE_RIDE_HANDLING_FEE
from pricing.functions import get_base_sharing_price, get_popularity_price, get_noisy_number_for_day_time
from datetime import datetime, date, timedelta, time
import calendar
from sharing.algo_api import calculate_route

ALGO_COMPUTATION_DELTA = timedelta(minutes=5)
FAX_HANDLING_DELTA = timedelta(minutes=2)
TOTAL_HANDLING_DELTA = ALGO_COMPUTATION_DELTA + FAX_HANDLING_DELTA

ORDERING_ALLOWED_PICKUP_DELTA = TOTAL_HANDLING_DELTA # + hotspot's dispatching time
ORDERING_ALLOWED_DROPOFF_DELTA = timedelta(minutes=60)

PICKUP = "pickup"
DROPOFF = "dropoff"

class HotSpot(BaseModel):
    name = models.CharField(_("hotspot name"), max_length=50)
    description = models.CharField(_("hotspot description"), max_length=100, null=True, blank=True)

    station = models.ForeignKey(Station, related_name="hotspots")
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

    def get_cost(self, lat, lon, day, t, num_seats=1):
        cost = None

        tarriff = None
        for ruleset in RuleSet.objects.all():
            if ruleset.is_active(day, t):
                tarriff = ruleset
                break

        ca1, ca2 = None, None
        if tarriff:
            for area in CityArea.objects.all():
                if area.contains(lat, lon):
                    ca1 = area
                if area.contains(self.lat, self.lon):
                    ca2 = area
                if ca1 and ca2:
                    break


        if ca1 and ca2:
            cost_rules = self.station.fixed_prices.filter(rule_set=tarriff)
            rules1 = cost_rules.filter(city_area_1=ca1, city_area_2=ca2)
            if rules1:
                return rules1[0].price
            else:
                rules2 = cost_rules.filter(city_area_1=ca2, city_area_2=ca1)
                if rules2:
                    return rules2[0].price


        # simpler but much slower implementation
#        active_rules = filter(lambda r: r.is_active(lat, lon, self.lat, self.lon, day, t), self.station.fixed_prices.all())
#        if active_rules:
#            cost = min([r.price for r in active_rules])

        return cost

    def get_meter_price(self, lat, lon, day, t, num_seats=1):
        result = calculate_route(self.lat, self.lon, lat, lon)
        estimated_duration, estimated_distance = result["estimated_duration"], result["estimated_distance"]

        cost, ride_type = estimate_cost(estimated_duration, estimated_distance, day=convert_python_weekday(day.weekday()), time=t)
        return round(cost + PRIVATE_RIDE_HANDLING_FEE) if cost else None

    def get_sharing_price(self, lat, lon, day, t, num_seats=1, with_popularity=False):
        """
        @param lat:
        @param lon:
        @param day: date of ride
        @param t: time of ride
        @param num_seats: number of seats
        @return: price as int or None
        """
        logging.info("calc sharing price for %s (lat=%s, lon=%s, day=%s, t=%s, seats=%s)" % (self.name, lat, lon, day, t, num_seats))

        cost = self.get_cost(lat, lon, day, t, num_seats)
        if not cost:
            logging.warning("no cost defined")
            return None, None if with_popularity else None

        if num_seats > 2:
            price = cost
        else:
            base_sharing_price = get_base_sharing_price(cost)

            # 1. first check for a custom price rule
            #noinspection PyUnresolvedReferences
            for rule_id in self.get_hotspotcustompricerule_order():
                rule = HotSpotCustomPriceRule.by_id(rule_id)

                if rule.is_active(lat, lon, day, t):
                    base_sharing_price = rule.price
                    logging.info("found custom price rule[%s] price=%s" % (rule.id, rule.price))
                    break

            # 2. tariff price rule
            else:
                logging.info("no custom price rule found")
                active_rule_set = RuleSet.get_active_set(day, t)
                if active_rule_set:
                    active_tariff_rules = self.tariff_rules.filter(rule_set=active_rule_set)
                    for rule in CityArea.relative_sort_models(active_tariff_rules):
                        if rule.is_active(lat, lon):
                            base_sharing_price = rule.price
                            logging.info("found tariff rule[%s] price=%s" % (rule.id, rule.price))
                            break
                    else:
                        logging.info("no tariff rule found")
                        logging.info("  --> using default sharing price: %s" % base_sharing_price)

            if num_seats == 2:
                delta = max([cost - base_sharing_price, 0])
                price = base_sharing_price + 0.5 * delta
            else:
                price = base_sharing_price

        # popularity
        pop_rule = self.get_popularity_rule(lat, lon, day, t)
        if pop_rule:
            logging.info("found popularity rule %s" % pop_rule.name)
            price = pop_rule.apply(price, day, t)
            popularity = pop_rule.popularity
        else:
            logging.info("  --> using default popularity")
            price = HotSpotPopularityRule.apply_default(price, day, t)
            popularity = HotSpotPopularityRule.get_default_popularity()

        # normalize
        if price:
            price = int(math.ceil(price))

        logging.info("sharing price: %s (cost: %s)" % (price, cost))

        if with_popularity:
            return price, popularity
        else:
            return price


    def get_popularity_rule(self, lat, lon, day, t):
        for pop_rule in self.popularity_rules.all():
            if pop_rule.is_active(lat, lon, day, t):
                return pop_rule

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
        hn = str(hn.groups()[0] if hn else 0)

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


class HotSpotPopularityRule(AbstractTemporalRule):
    DEFAULT_POPULARITY = 10
    DEFAULT_NOISELIMIT = 20

    MaxPopularity = 100
    MaxNoiseLimit = 100

    hotspot = models.ForeignKey(HotSpot, verbose_name=_("hotspot"), related_name="popularity_rules")
    city_area = CityAreaField(verbose_name=_("city area"))
    _popularity = models.IntegerField(verbose_name=_("popularity"), default=DEFAULT_POPULARITY,
        validators=[MinValueValidator(0), MaxValueValidator(MaxPopularity)])
    noise_limit = models.IntegerField(verbose_name=_("noise limit"), default=DEFAULT_NOISELIMIT,
        validators=[MinValueValidator(0), MaxValueValidator(MaxNoiseLimit)])

    @property
    def popularity(self):
        return self._popularity / float(self.MaxPopularity)

    @classmethod
    def get_default_popularity(cls):
        return cls.DEFAULT_POPULARITY / float(cls.MaxPopularity)

    def is_active(self, lat, lon, day, t):
        in_city_area = self.city_area.contains(lat, lon)
        return in_city_area and super(HotSpotPopularityRule, self).is_active(day, t)

    def apply(self, price, day, t):
        return self.__class__._apply_popularity(price, day, t, self.popularity, self.noise_limit)

    @classmethod
    def apply_default(cls, price, day, t):
        return cls._apply_popularity(price, day, t, cls.DEFAULT_POPULARITY, cls.DEFAULT_NOISELIMIT)

    @classmethod
    def _apply_popularity(cls, price, day, t, popularity, noise_limit):
        popularity /= float(cls.MaxPopularity)
        noise_limit /= float(cls.MaxNoiseLimit)

        noisy_popularity = cls._noisify_popularity(popularity, noise_limit, day, t)
        logging.info("popularity=%s, noise limit=%s --> noisy popularity=%s" % (popularity, noise_limit, noisy_popularity))

        price = get_popularity_price(noisy_popularity, price)
        return price

    @classmethod
    def _noisify_popularity(cls, popularity, noise_limit, day, t):
        return get_noisy_number_for_day_time(popularity, noise_limit, day, t)


class HotSpotCustomPriceRule(AbstractTemporalRule):
    hotspot = models.ForeignKey(HotSpot, verbose_name=_("hotspot"), related_name="custom_rules")
    city_area = CityAreaField(verbose_name=_("city area"))
    price = models.FloatField(_("price"))

    class Meta:
        order_with_respect_to = 'hotspot'

    def is_active(self, lat, lon, day, t):
        in_city_area = self.city_area.contains(lat, lon)
        return in_city_area and super(HotSpotCustomPriceRule, self).is_active(day, t)


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
