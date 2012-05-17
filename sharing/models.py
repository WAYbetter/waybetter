import logging
import re
import math
from common.decorators import order_relative_to_field, mute_logs
from common.tz_support import default_tz_now, to_task_name_safe, ceil_datetime, floor_datetime
from common.util import phone_validator
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from common.util import convert_python_weekday, datetimeIterator
from common.models import BaseModel, Country, City, CityAreaField, CityArea
from django.core.validators import MaxValueValidator, MinValueValidator
from ordering.models import Passenger, Station, OrderType
from pricing.models import RuleSet, AbstractTemporalRule, PRIVATE_RIDE_HANDLING_FEE
from pricing.functions import get_base_sharing_price, get_popularity_price, get_noisy_number_for_day_time
from datetime import datetime, date, timedelta, time
import calendar

ALGO_COMPUTATION_DELTA = timedelta(minutes=5)
FAX_HANDLING_DELTA = timedelta(minutes=2)
TOTAL_HANDLING_DELTA = ALGO_COMPUTATION_DELTA + FAX_HANDLING_DELTA

class HotSpot(BaseModel):
    name = models.CharField(_("hotspot name"), max_length=50)
    description = models.CharField(_("hotspot description"), max_length=100, null=True, blank=True)
    priority = models.FloatField(_("priority"), unique=True, default=0)

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

    def order_processing_time(self, order_type):
        handling_time = TOTAL_HANDLING_DELTA
        if order_type == OrderType.PRIVATE:
            handling_time -= ALGO_COMPUTATION_DELTA

        return handling_time + timedelta(minutes=self.dispatching_time)

    def get_cost(self, lat, lon, day, t, num_seats=1, tariff_rules=None, cost_rules=None):
        tarriff = None
        if tariff_rules is None:
            tariff_rules = RuleSet.objects.all()

        for ruleset in tariff_rules:
            if ruleset.is_active(day, t):
                tarriff = ruleset
                break

        if not tarriff:
            logging.error("no tariff found day=%s, t=%s" % (day, t))
            return None

        active_cost_rule = None
        if cost_rules is not None:
            active_rules = filter(lambda r: r.rule_set == tarriff, cost_rules)
            if active_rules:
                active_cost_rule = active_rules[0]
        else:
            ca1, ca2 = None, None
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
                    active_cost_rule = rules1[0]
                else:
                    rules2 = cost_rules.filter(city_area_1=ca2, city_area_2=ca1)
                    if rules2:
                        active_cost_rule = rules2[0]

        if active_cost_rule:
            return active_cost_rule.price
        else:
            return None

    def get_meter_price(self, lat, lon, day, t, num_seats=1):
        from sharing.algo_api import calculate_route

        result = calculate_route(self.lat, self.lon, lat, lon)
        estimated_duration, estimated_distance = result["estimated_duration"], result["estimated_distance"]

        from ordering.pricing import estimate_cost
        cost, ride_type = estimate_cost(estimated_duration, estimated_distance, day=convert_python_weekday(day.weekday()), time=t)
        return round(cost + PRIVATE_RIDE_HANDLING_FEE) if cost else None

    def get_sharing_price(self, lat, lon, day, t, num_seats=1, with_popularity=False, tariff_rules=None, cost_rules=None, pop_rules=None):
        """
        @param lat:
        @param lon:
        @param day: date of ride
        @param t: time of ride
        @param num_seats: number of seats
        @param tariff_rules: a list of rules to check against
        @param cost_rules: a list of rules to check against
        @return: price or (price, popularity). both may be None
        """
        logging.info("calc sharing price for %s (lat=%s, lon=%s, day=%s, t=%s, seats=%s)" % (self.name, lat, lon, day, t, num_seats))

        cost = self.get_cost(lat, lon, day, t, num_seats, tariff_rules, cost_rules)
        if not cost:
            logging.warning("no cost defined")
            return (None, None) if with_popularity else None

        base_sharing_price = get_base_sharing_price(cost)

        pop_rule = self.get_popularity_rule(day, t, pop_rules=pop_rules)
        if pop_rule:
            logging.info("found popularity rule %s" % pop_rule.name)
            pop_price = pop_rule.apply(base_sharing_price, day, t)
            popularity = pop_rule.popularity
        else:
            logging.info("  --> using default popularity")
            pop_price = HotSpotPopularityRule.apply_default(base_sharing_price, day, t)
            popularity = HotSpotPopularityRule.get_default_popularity()

        if num_seats > 2:
            price = base_sharing_price
        elif num_seats == 2:
            delta = max([base_sharing_price - pop_price, 0])
            price = pop_price + 0.4 * delta
        else:
            price = pop_price

        # normalize
        if price:
            price = int(math.ceil(price))

        logging.info("sharing price: %s (cost: %s)" % (price, cost))

        if with_popularity:
            return price, popularity
        else:
            return price


    @mute_logs()
    def get_offers(self, lat, lon, day, num_seats=1):
        now = default_tz_now()
        start_time = self.get_next_orderable_interval().time() if day == now.date() else None

        ca1, ca2 = None, None
        for area in CityArea.objects.all():
            if area.contains(lat, lon):
                ca1 = area
            if area.contains(self.lat, self.lon):
                ca2 = area

        pop_rules = list(self.popularity_rules.all())
        tariffs = list(RuleSet.objects.all())
        costs1 = list(self.station.fixed_prices.filter(city_area_1=ca1, city_area_2=ca2))
        costs2 = list(self.station.fixed_prices.filter(city_area_1=ca2, city_area_2=ca1))
        costs = costs1 + costs2

        offers = []

        if day == now.date():
            # order WILL NOT be sent to algo. add 2 min. spare time for booking process
            asap_interval = ceil_datetime(now + self.order_processing_time(OrderType.PRIVATE) + timedelta(minutes=2))
            if self.get_next_orderable_interval() > asap_interval:
                t = asap_interval.time()
                cost = self.get_cost(lat, lon, day, t, num_seats, tariffs, costs)
                if cost:
                    asap_price = get_base_sharing_price(cost)
                    offers.append({'time': t, 'price': asap_price, 'popularity': 0, 'type': OrderType.PRIVATE})

        for t in self.get_times_for_day(day, start_time=start_time):
            price, popularity = self.get_sharing_price(lat, lon, day, t, num_seats, True, tariffs, costs, pop_rules)
            if price is not None:
                offers.append({'time': t, 'price': price, 'popularity': popularity, 'type': OrderType.SHARED})

        return offers


    def get_popularity_rule(self, day, t, pop_rules=None):
        if pop_rules is None:
            pop_rules = self.popularity_rules.all()
        for pop_rule in pop_rules:
            if pop_rule.is_active(day, t):
                return pop_rule

        return None

    def get_next_orderable_interval(self):
        return self.get_next_interval(base_time=default_tz_now() + self.order_processing_time(OrderType.SHARED))

    def get_next_interval(self, base_time=None, timeframe=timedelta(weeks=1)):
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
    TIME_INTERVAL_CHOICES = [(5, "5 min"), (10, "10 min"), (15, "15 min"), (20, "20 min"), (30, "30 min"), (60, "1 hour")]
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
    DEFAULT_POPULARITY = 0
    DEFAULT_NOISELIMIT = 10

    MaxPopularity = 100
    MaxNoiseLimit = 100

    hotspot = models.ForeignKey(HotSpot, verbose_name=_("hotspot"), related_name="popularity_rules")
    _popularity = models.IntegerField(verbose_name=_("popularity"), default=DEFAULT_POPULARITY,
        validators=[MinValueValidator(0), MaxValueValidator(MaxPopularity)])
    _noise_limit = models.IntegerField(verbose_name=_("noise limit"), default=DEFAULT_NOISELIMIT,
        validators=[MinValueValidator(0), MaxValueValidator(MaxNoiseLimit)])

    @property
    def popularity(self):
        return self._popularity / float(self.MaxPopularity)

    @property
    def noise_limit(self):
        return self._noise_limit / float(self.MaxNoiseLimit)

    @classmethod
    def get_default_popularity(cls):
        return cls.DEFAULT_POPULARITY / float(cls.MaxPopularity)

    @classmethod
    def get_default_noise_limit(cls):
        return cls.DEFAULT_NOISELIMIT / float(cls.MaxNoiseLimit)

    def apply(self, base_price, day, t):
        return self.__class__._apply_popularity(base_price, day, t, self.popularity, self.noise_limit)

    @classmethod
    def apply_default(cls, base_price, day, t):
        return cls._apply_popularity(base_price, day, t, cls.get_default_popularity(), cls.get_default_noise_limit())

    @classmethod
    def _apply_popularity(cls, base_price, day, t, popularity, noise_limit):
        noisy_popularity = cls._noisify_popularity(popularity, noise_limit, day, t)
        logging.info("popularity=%s, noise limit=%s --> noisy popularity=%s" % (popularity, noise_limit, noisy_popularity))

        price = get_popularity_price(noisy_popularity, base_price)
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
