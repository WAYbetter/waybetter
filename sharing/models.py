from django.db import models
from django.utils.translation import ugettext_lazy as _, ugettext
from djangotoolbox.fields import BlobField, ListField
from common.models import BaseModel, Country, City, CityArea
from common.tz_support import UTCDateTimeField
from ordering.models import DAY_OF_WEEK_CHOICES

class HotSpot(BaseModel):
    name = models.CharField(_("hotspot name"), max_length=50)

    country = models.ForeignKey(Country, verbose_name=_("country"), related_name="stations")
    city = models.ForeignKey(City, verbose_name=_("city"), related_name="stations")
    address = models.CharField(_("address"), max_length=80)
    geohash = models.CharField(_("goehash"), max_length=13)
    lon = models.FloatField(_("longtitude"), null=True)
    lat = models.FloatField(_("latitude"), null=True)


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

    interval = models.IntegerField(_("time interval"), choices=TIME_INTERVAL_CHOICES)