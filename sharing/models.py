from django.db import models
from django.utils.translation import ugettext_lazy as _
from common.util import convert_python_weekday, datetimeIterator
from common.models import BaseModel, Country, City, CityArea
from pricing.models import RuleSet, AbstractTemporalRule
from datetime import datetime, date, timedelta, time
import calendar

class HotSpot(BaseModel):
    name = models.CharField(_("hotspot name"), max_length=50)

    country = models.ForeignKey(Country, verbose_name=_("country"), related_name="hotspots")
    city = models.ForeignKey(City, verbose_name=_("city"), related_name="hotspots")
    address = models.CharField(_("address"), max_length=80)
    geohash = models.CharField(_("goehash"), max_length=13)
    lon = models.FloatField(_("longtitude"), null=True)
    lat = models.FloatField(_("latitude"), null=True)

    def get_price(self, lat, lon, day, t):
        #noinspection PyUnresolvedReferences
        for rule_id in self.get_hotspotpricerule_order():
            rule = HotSpotCustomPriceRule.by_id(rule_id)

            if rule.city_area.contains(lat, lon) and rule.is_active(day, t):
                return rule.price

        return None


    def get_times(self, day=None, start_time=None, end_time=None):
        d = day or date.today()

        times = set()
        for rule in self.service_rules.all():
            if rule.is_active(day=d, t=None): # rule is active on day
                times.update(rule.get_times(start_time, end_time))

        return sorted(times)

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
            dates.update(rule.get_dates())

        itr = datetimeIterator(start_date, end_date)
        for d in itr:
            if convert_python_weekday(d.weekday()) in weekdays:
                dates.add(d)

        return list(dates)


class HotSpotServiceRule(AbstractTemporalRule):
    TIME_INTERVAL_CHOICES = [(5, "5 min"), (10, "10 min"), (15, "15 min"), (30, "30 min"), (60, "1 hour")]
    hotspot = models.ForeignKey(HotSpot, verbose_name=_("hotspot"), related_name="service_rules")
    interval = models.IntegerField(_("time interval"), choices=TIME_INTERVAL_CHOICES) # minutes

    def __init__(self, *args, **kwargs):
        super(AbstractTemporalRule, self).__init__(*args, **kwargs)
        self.rule_set = None


    def get_times(self, start_time=None, end_time=None):
        """
        Times the rule is active on the days it is active.
        @param start_time: a datetime.time lower bound.
        @param end_time: a datetime.time upper bound.
        @return: a list of times.
        """
        t1 = start_time or time.min
        t2 = end_time or time.max

        from_datetime = datetime.combine(date.today(), self.from_hour)
        to_datetime = datetime.combine(date.today(), self.to_hour)

        times = []
        itr = datetimeIterator(from_datetime, to_datetime, delta=timedelta(minutes=self.interval))
        for d in itr:
            t = d.time()
            if t1 <= t <= t2:
                times.append(t)

        return times


class HotSpotCustomPriceRule(AbstractTemporalRule):
    hotspot = models.ForeignKey(HotSpot, verbose_name=_("hotspot"), related_name="custom_rules")
    city_area = models.ForeignKey(CityArea, verbose_name=_("city area"))
    price = models.FloatField(_("price"))

    class Meta:
        order_with_respect_to = 'hotspot'

    def __init__(self, *args, **kwargs):
        super(AbstractTemporalRule, self).__init__(*args, **kwargs)
        self.rule_set = None

    def is_active(self, lat, lon, day, t):
        return self.city_area.contains(lat, lon) and super(AbstractTemporalRule, self).is_active(day, t)


class HotSpotTariffRule(BaseModel):
    hotspot = models.ForeignKey(HotSpot, verbose_name=_("hotspot"), related_name="tariff_rules")
    rule_set = models.ForeignKey(RuleSet, verbose_name=_("rule set"))
    city_area = models.ForeignKey(CityArea, verbose_name=_("city area"))
    price = models.FloatField(_("price"))

    def is_active(self, lat, lon, day, t):
        return self.city_area.contains(lat, lon) and self.rule_set.is_active(day, t)


class HotSpotTag(BaseModel):
    name = models.CharField(_("tag"), max_length=50)
    hotspot = models.ForeignKey(HotSpot, verbose_name=_("hotspot"), related_name="tags")