from django.db import models
from django.utils.translation import gettext_lazy as _

from ordering.models import Order, WorkStation, Station, OrderAssignment, Passenger
from common.util import EventType
from common.models import Country, City

class AnalyticsEvent(models.Model):
    type = models.IntegerField(_("type"), choices=EventType.choices())

    order = models.ForeignKey(Order, verbose_name=_("order"), related_name="events", null=True, blank=True)
    order_assignment = models.ForeignKey(OrderAssignment, verbose_name=_("order assignment"), related_name="events", null=True, blank=True)
    work_station = models.ForeignKey(WorkStation, verbose_name=_("work station"), related_name="events", null=True, blank=True)
    station = models.ForeignKey(Station, verbose_name=_("station"), related_name="events", null=True, blank=True)
    passenger = models.ForeignKey(Passenger, verbose_name=_("passenger"), related_name="events", null=True, blank=True)
    country = models.ForeignKey(Country, verbose_name=_("country"), related_name="events", null=True, blank=True)
    city = models.ForeignKey(City, verbose_name=_("city"), related_name="events", null=True, blank=True)

    create_date = models.DateTimeField(_("create date"), auto_now_add=True)
    modify_date = models.DateTimeField(_("modify date"), auto_now=True)

    def save(self, force_insert=False, force_update=False, using=None):
        self.full_clean() # validates model
        super(AnalyticsEvent, self).save()

    def get_label(self):
        return EventType.get_label(self.type)
