from django.db import models
from django.utils.translation import ugettext_lazy as _

from common.models import BaseModel
from common.tz_support import UTCDateTimeField
from common.util import Enum
from ordering.models import Station

class StopType(Enum):
    PICKUP  = 0
    DROPOFF = 1
    
class Driver(BaseModel):
    create_date = UTCDateTimeField(_("create date"), auto_now_add=True)
    modify_date = UTCDateTimeField(_("modify date"), auto_now=True)

    station = models.ForeignKey(Station, verbose_name=_("station"), related_name="drivers")
    name = models.CharField(_("name"), max_length=140, null=True, blank=True)
    

class SharedRide(BaseModel):
    create_date = UTCDateTimeField(_("create date"), auto_now_add=True)
    modify_date = UTCDateTimeField(_("modify date"), auto_now=True)

    depart_time = UTCDateTimeField(_("depart time"))
    arrive_time = UTCDateTimeField(_("arrive time"))

    station = models.ForeignKey(Station, verbose_name=_("station"), related_name="rides", null=True, blank=True)
#    driver = models.ForeignKey(Driver, verbose_name=_("driver"), related_name="rides", null=True, blank=True)


class RidePoint(BaseModel):
    create_date = UTCDateTimeField(_("create date"), auto_now_add=True)
    modify_date = UTCDateTimeField(_("modify date"), auto_now=True)

    ride = models.ForeignKey(SharedRide, verbose_name=_("ride"), related_name="points", null=True, blank=True)

    stop_time = UTCDateTimeField(_("stop time"))
    type = models.IntegerField(_("type"), choices=StopType.choices(), default=0)

    lon = models.FloatField(_("longtitude"))
    lat = models.FloatField(_("latitude"))
    address = models.CharField(_("address"), max_length=200, null=True, blank=True)

