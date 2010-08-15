from django.db import models
from django.utils.translation import gettext_lazy as _



# Create your models here.
from django.contrib.auth.models import User
from common.models import Country, City, CityArea

ASSIGNED = 1
ACCEPTED = 2
IGNORED = 3
REJECTED = 4
PENDING = 5
FAILED = 6 
ERROR = 7

ASSIGNMENT_STATUS = ((ASSIGNED, _("assigned")),
                     (ACCEPTED, _("accepted")),
                     (IGNORED, _("ignored")),
                     (REJECTED, _("rejected")))

ORDER_STATUS = ASSIGNMENT_STATUS + ((PENDING, _("pending")),
                                    (FAILED, _("failed")),
                                    (ERROR, _("error"))) 

class Passenger(models.Model):
    user = models.OneToOneField(User, verbose_name=_("user"), related_name="passenger")

    phone = models.CharField(_("phone number"), max_length=15)
    phone_verification_code = models.IntegerField(_("phone verification code"), max_length=5)
    phone_verified = models.BooleanField(_("phone verified"))

    create_date = models.DateTimeField(_("create date"), auto_now_add=True)
    modify_date = models.DateTimeField(_("modify date"), auto_now=True)

    def __unicode__(self):
        return self.user.username


class Station(models.Model):
    user = models.OneToOneField(User, verbose_name=_("user"), related_name="station")

    name = models.CharField(_("station name"), max_length=50)
    phone = models.CharField(_("phone number"), max_length=15)

    # validator must ensure city.country == country and city_area = city.city_area
    country = models.ForeignKey(Country, verbose_name=_("country"), related_name="stations")
    city = models.ForeignKey(City, verbose_name=_("city"), related_name="stations")
    city_area = models.ForeignKey(CityArea, verbose_name=_("city area"), related_name="stations", null=True, blank=True)
    postal_code = models.CharField(_("postal code"), max_length=10)
    address = models.CharField(_("address"), max_length=50)
    geohash = models.CharField(_("goehash"), max_length=13)

    create_date = models.DateTimeField(_("create date"), auto_now_add=True)
    modify_date = models.DateTimeField(_("modify date"), auto_now=True)

    def natural_key(self):
        return self.name
        
    def __unicode__(self):
        return self.name

class WorkStation(models.Model):
    user = models.OneToOneField(User, verbose_name=_("user"), related_name="work_station")

    station = models.ForeignKey(Station, verbose_name=_("station"), related_name="work_stations")
    token = models.CharField(_("token"), max_length=20)
    im_user = models.CharField(_("instant messaging username"), null=True, blank=True, max_length=40)

    def __unicode__(self):
        return u"Workstation "# of: %d" % (self.station.id)


class Order(models.Model):

    passenger = models.ForeignKey(Passenger, verbose_name=_("passenger"), related_name="orders", null=True, blank=True)
    station = models.ForeignKey(Station, verbose_name=_("station"), related_name="orders", null=True, blank=True)

    status = models.IntegerField(_("status"), choices=ORDER_STATUS, default=PENDING)

    from_country = models.ForeignKey(Country, verbose_name=_("from country"), related_name="orders_from")
    from_city = models.ForeignKey(City, verbose_name=_("from city"), related_name="orders_from")
    from_city_area = models.ForeignKey(CityArea, verbose_name=_("from city area"), related_name="orders_from", null=True, blank=True)
    from_postal_code = models.CharField(_("from postal code"), max_length=10, null=True, blank=True)
    from_street_address = models.CharField(_("from street address"), max_length=50)
    from_geohash = models.CharField(_("from goehash"), max_length=13)
    from_lon = models.FloatField(_("from_lon"))
    from_lat = models.FloatField(_("from_lat"))
    from_raw = models.CharField(_("from address"), max_length=50)
    # this field holds the data as typed by the user
    to_country = models.ForeignKey(Country, verbose_name=_("to country"), related_name="orders_to")

    to_city = models.ForeignKey(City, verbose_name=_("to city"), related_name="orders_to")
    to_city_area = models.ForeignKey(CityArea, verbose_name=_("to city area"), related_name="orders_to", null=True, blank=True)
    to_postal_code = models.CharField(_("to postal code"), max_length=10, null=True, blank=True)
    to_street_address = models.CharField(_("to street address"), max_length=50)
    to_geohash = models.CharField(_("to goehash"), max_length=13)
    to_lon = models.FloatField(_("to_lon"))
    to_lat = models.FloatField(_("to_lat"))
    # this field holds the data as typed by the user
    to_raw = models.CharField(_("to address"), max_length=50)

    pickup_time = models.IntegerField(_("pickup time"), null=True, blank=True)

    create_date = models.DateTimeField(_("create date"), auto_now_add=True)
    modify_date = models.DateTimeField(_("modify date"), auto_now=True)
    
    def __unicode__(self):
        return u"%s from %s to %s" % (_("order"), self.from_raw, self.to_raw)

    def get_status_label(self):
        for key, label in ORDER_STATUS:
            if key == self.status:
                return label

        raise ValueError("invalid status")
    
    
class OrderAssignment(models.Model):
    order = models.ForeignKey(Order, verbose_name=_("order"), related_name="assignments")
    work_station = models.ForeignKey(WorkStation, verbose_name=_("wokr station"), related_name="assignments")
    station = models.ForeignKey(Station, verbose_name=_("station"), related_name="assignments")
    
    status = models.IntegerField(_("status"), choices=ASSIGNMENT_STATUS, default=ASSIGNED)

    create_date = models.DateTimeField(_("create date"), auto_now_add=True)
    modify_date = models.DateTimeField(_("modify date"), auto_now=True)

    def __unicode__(self):
        order_id = "Unknown"
        if self.order:
            order_id =str(self.order)
            
        return u"%s #%s %s %s" % (_("order"), order_id, _("assigned to station:"), self.station)

    