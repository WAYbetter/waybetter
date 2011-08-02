import calendar
from common.util import split_to_tuples, point_inside_polygon
from django.db import models
from django.utils.translation import ugettext_lazy as _
from common.util import DAY_OF_WEEK_CHOICES, FIRST_WEEKDAY, LAST_WEEKDAY, convert_python_weekday, datetimeIterator
from datetime import datetime, date, timedelta, time
from common.models import BaseModel, Country, City
from sharing.widgets import ListFieldWithUI, ColorField

class HotSpot(BaseModel):
    name = models.CharField(_("hotspot name"), max_length=50)

    country = models.ForeignKey(Country, verbose_name=_("country"), related_name="stations")
    city = models.ForeignKey(City, verbose_name=_("city"), related_name="stations")
    address = models.CharField(_("address"), max_length=80)
    geohash = models.CharField(_("goehash"), max_length=13)
    lon = models.FloatField(_("longtitude"), null=True)
    lat = models.FloatField(_("latitude"), null=True)

    def get_area_for_point(self, lat, lon):
        #noinspection PyUnresolvedReferences
        for area_id in self.get_pricearea_order():
            area = PriceArea.by_id(area_id)
            if area.is_in_area(lat, lon):
                return area

        return None

    def get_times(self, day=None, start_time=None, end_time=None):
        day = day or date.today()

        times = set()
        for tf in self.time_frames.all():
            if tf.is_active(day):
                times.update(tf.get_times(start_time, end_time))

        return sorted(times)

    def get_dates_for_month(self, year, month):
        start_date = date(year, month, 1)
        end_date = date(year, month, calendar.monthrange(year, month)[1]) # last day of month
        return self.get_dates(start_date, end_date)


    def get_dates(self, start_date, end_date):
        """
        @param start_date: datetime.date instance
        @param end_date: datetime.date instance
        @return: a list of dates withing the given date range in which the hotspot is active.
        """
        weekdays = set()
        dates = set()

        for tf in self.time_frames.all():
            if tf.from_weekday and tf.to_weekday:
                weekdays.update(tf.get_weekdays())

            elif tf.from_date and tf.to_date:
                itr = datetimeIterator(max(start_date, tf.from_date), min(end_date, tf.to_date))
                dates.update(list(itr))

        itr = datetimeIterator(start_date, end_date)
        for d in itr:
            if convert_python_weekday(d.weekday()) in weekdays:
                dates.add(d)

        return list(dates)


class HotSpotTag(BaseModel):
    name = models.CharField(_("tag"), max_length=50)
    hotspot = models.ForeignKey(HotSpot, verbose_name=_("hotspot"), related_name="tags")


class HotSpotTimeFrame(BaseModel):
    TIME_INTERVAL_CHOICES = [(5, "5 min"), (10, "10 min"), (15, "15 min"), (30, "30 min")]

    hotspot = models.ForeignKey(HotSpot, verbose_name=_("hotspot"), related_name="time_frames")

    from_date = models.DateField(_("from date"), null=True, blank=True)
    to_date = models.DateField(_("to date"), null=True, blank=True)

    from_weekday = models.IntegerField(_("from day"), choices=DAY_OF_WEEK_CHOICES, null=True, blank=True)
    to_weekday = models.IntegerField(_("to day"), choices=DAY_OF_WEEK_CHOICES, null=True, blank=True)

    from_hour = models.TimeField(_("from hour"))
    to_hour = models.TimeField(_("to hour"))

    interval = models.IntegerField(_("time interval"), choices=TIME_INTERVAL_CHOICES) # minutes

    def is_active(self, day):
        if self.from_date and self.to_date:
            return self.from_date <= day <= self.to_date
        else:
            return convert_python_weekday(day.weekday()) in self.get_weekdays()

    def get_times(self, start_time=None, end_time=None):
        start_time = start_time or time.min
        end_time = end_time or time.max

        from_datetime = datetime.combine(date.today(), self.from_hour)
        to_datetime = datetime.combine(date.today(), self.to_hour)

        times = []
        itr = datetimeIterator(from_datetime, to_datetime, delta=timedelta(minutes=self.interval))
        for d in itr:
            t = d.time()
            if start_time <= t <= end_time:
                times.append(t)

        return times

    def get_weekdays(self):
        weekdays = []
        if self.from_weekday and self.to_weekday:
            if self.from_weekday < self.to_weekday:
                weekdays = range(self.from_weekday, self.to_weekday + 1)
            else:
                weekdays = range(self.from_weekday, LAST_WEEKDAY + 1) + range(FIRST_WEEKDAY, self.to_weekday + 1)

        return weekdays


class PriceArea(BaseModel):
    points = ListFieldWithUI(models.FloatField(), verbose_name=_("Edit Points"), null=True, blank=True)
    color = ColorField(default="yellow")
    cost = models.FloatField()
    price = models.FloatField(null=True, blank=True)
    name = models.CharField(_("name"), max_length=50)

    hotspot = models.ForeignKey(HotSpot, verbose_name=_("hotspot"), related_name="areas")

    class Meta:
        order_with_respect_to = 'hotspot'

    def is_in_area(self, lat, lon):
        return point_inside_polygon(lat, lon, self.polygon)

    @property
    def polygon(self):
        #TODO_WB: refactor into polygon class
        return list(split_to_tuples(self.points, 2))
