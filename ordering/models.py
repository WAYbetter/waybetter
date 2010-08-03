from django.db import models
from django.utils.translation import gettext_lazy as _



# Create your models here.
from django.contrib.auth.models import User
from common.models import Country, City, CityArea

PENDING = _("pending")
ASSIGNED = _("assigned")
ACCEPTED = _("accepted")
IGNORED = _("ignored")
REJECTED = _("rejected")

ASSIGNMENT_STATUS = ((1, ASSIGNED),
                     (2, ACCEPTED),
                     (3, IGNORED),
                     (4, REJECTED))

ORDER_STATUS = ASSIGNMENT_STATUS + ((5, PENDING),) # notice the ,



class Passenger(models.Model):
    user = models.ForeignKey(User, verbose_name=_("user"), related_name="passenger")

    phone = models.CharField(_("phone number"), max_length=15)
    phone_verification_code = models.IntegerField(_("phone verification code"), max_length=5)
    phone_verified = models.BooleanField(_("phone verified"))

    create_date = models.DateTimeField(_("create date"), auto_now_add=True)
    modify_date = models.DateTimeField(_("modify date"), auto_now=True)

    def __unicode__(self):
        return self.user.username


class Station(models.Model):
    user = models.ForeignKey(User, verbose_name=_("user"), related_name="station")

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
    
    def __unicode__(self):
        return self.name

class Dispatcher(models.Model):
    station = models.ForeignKey(Station, verbose_name=_("station"), related_name="dispatchers")
    token = models.CharField(_("token"), max_length=20)

class Order(models.Model):
    passenger = models.ForeignKey(Passenger, verbose_name=_("passenger"), related_name="orders", null=True, blank=True)
    station = models.ForeignKey(Station, verbose_name=_("station"), related_name="orders", null=True, blank=True)

    status = models.IntegerField(_("status"), choices=ORDER_STATUS, default=PENDING)

    from_country = models.ForeignKey(Country, verbose_name=_("from country"), related_name="orders_from")
    from_city = models.ForeignKey(City, verbose_name=_("from city"), related_name="orders_from")
    from_city_area = models.ForeignKey(CityArea, verbose_name=_("from city area"), related_name="orders_from")
    from_postal_code = models.CharField(_("from postal code"), max_length=10)
    from_address = models.CharField(_("from address"), max_length=50)
    from_geohash = models.CharField(_("from goehash"), max_length=13)

    to_country = models.ForeignKey(Country, verbose_name=_("to country"), related_name="orders_to")
    to_city = models.ForeignKey(City, verbose_name=_("to city"), related_name="orders_to")
    to_city_area = models.ForeignKey(CityArea, verbose_name=_("to city area"), related_name="orders_to")
    to_postal_code = models.CharField(_("to postal code"), max_length=10)
    to_address = models.CharField(_("to address"), max_length=50)
    to_geohash = models.CharField(_("to goehash"), max_length=13)

    pickup_time = models.IntegerField(_("pickup time"), null=True, blank=True)

    create_date = models.DateTimeField(_("create date"), auto_now_add=True)
    modify_date = models.DateTimeField(_("modify date"), auto_now=True)
    
    def __unicode__(self):
        return u"%s #%d" % (_("order"), self.id)
    
    
class OrderAssignment(models.Model):
    order = models.ForeignKey(Order, verbose_name=_("order"), related_name="assignments")
    dispatcher = models.ForeignKey(Dispatcher, verbose_name=_("dispatcher"), related_name="assignments")
    station = models.ForeignKey(Station, verbose_name=_("station"), related_name="assignments")
    
    status = models.IntegerField(_("status"), choices=ASSIGNMENT_STATUS, default=ASSIGNED)

    create_date = models.DateTimeField(_("create date"), auto_now_add=True)
    modify_date = models.DateTimeField(_("modify date"), auto_now=True)

    def __unicode__(self):
        return u"%s #%d %s %s" % (_("order"), self.order.id, _("assigned to station"), self.station)

    