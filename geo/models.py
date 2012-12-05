from django.conf import settings
from django.db import models
from django.utils.translation import ugettext_lazy as _

from common.models import Country, City
from geo.enums import PlaceType

class GoogleBounds(object):
    def __init__(self, values):
        self.sw_lat = values.get("sw_lat")
        self.sw_lon = values.get("sw_lon")
        self.ne_lon = values.get("ne_lon")
        self.ne_lat = values.get("ne_lat")

    def to_query_string(self):
        return "%s,%s|%s,%s" % (self.sw_lat, self.sw_lon, self.ne_lat, self.ne_lon)


class Place(models.Model):
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255)
    type = models.IntegerField(choices=PlaceType.choices())

    country = models.ForeignKey(Country, related_name="places")
    city = models.ForeignKey(City, related_name="places")
    street = models.CharField(max_length=50, null=True, blank=True)
    house_number = models.CharField(max_length=10, null=True, blank=True)

    lon = models.FloatField()
    lat = models.FloatField()

    @property
    def address(self):
        if self.street and self.house_number:
            return "%s %s, %s" % (self.street, self.house_number, self.city.name)
        else:
            return ""

    def save(self, *args, **kwargs):
        if not self.country:
            self.country = Country.objects.get(code=settings.DEFAULT_COUNTRY_CODE)

        if self.street and self.house_number:
            self.type = PlaceType.STREET_ADDRESS
        else:
            self.type = PlaceType.POI

        super(Place, self).save(*args, **kwargs)