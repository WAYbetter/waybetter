from django.db import models
from django.utils.translation import ugettext_lazy as _
from common.models import BaseModel, Country, City
from ordering.models import  Station
from datetime import   timedelta

FAX_HANDLING_DELTA = timedelta(minutes=2)

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

