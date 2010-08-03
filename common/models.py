from django.db import models
from django.utils.translation import gettext_lazy as _
                               
# Create your models here.
class Country(models.Model):
    name = models.CharField(_("name"), max_length=30)

    def __unicode__(self):
        return self.name



class City(models.Model):
    name = models.CharField(_("name"), max_length=50)
    country = models.ForeignKey(Country, verbose_name=_("country"), related_name="cities")

    def __unicode__(self):
        return self.name


class CityArea(models.Model):
    name = models.CharField(_("name"), max_length=50)
    city = models.ForeignKey(City, verbose_name=_("city"), related_name="city_areas")

    def __unicode__(self):
        return self.name