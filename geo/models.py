from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from common.models import BaseModel, Country, City
from djangotoolbox.fields import ListField
from geo.enums import PlaceType

class GoogleBounds(object):
    def __init__(self, values):
        self.sw_lat = values.get("sw_lat")
        self.sw_lon = values.get("sw_lon")
        self.ne_lon = values.get("ne_lon")
        self.ne_lat = values.get("ne_lat")

    def to_query_string(self):
        return "%s,%s|%s,%s" % (self.sw_lat, self.sw_lon, self.ne_lat, self.ne_lon)


class Place(BaseModel):
    type = models.IntegerField(choices=PlaceType.choices())

    name = models.CharField(max_length=255)
    name_for_station = models.CharField(max_length=255)
    name_for_user = models.CharField(max_length=255, default=name)

    description = models.CharField(max_length=255)
    description_for_station = models.CharField(max_length=255)
    description_for_user = models.CharField(max_length=255, default=description)

    aliases = ListField(models.CharField(max_length=32))

    country = models.ForeignKey(Country, related_name="places")
    city = models.ForeignKey(City, related_name="places")
    street = models.CharField(max_length=50, blank=True)
    house_number = models.CharField(max_length=10, blank=True)

    lon = models.FloatField()
    lat = models.FloatField()

    dn_country_name = models.CharField(max_length=255)
    dn_city_name = models.CharField(max_length=255)

    @property
    def address(self):
        if self.street and self.house_number:
            return "%s %s, %s" % (self.street, self.house_number, self.city.name)
        else:
            return ""

    def save(self, *args, **kwargs):
        if self.name == '':
            raise ValidationError('Name is required')

        self.name_for_station = self.name_for_user = self.name
        self.description_for_station = self.description_for_user = self.description

        self.country = Country.objects.get(code=settings.DEFAULT_COUNTRY_CODE)
        self.dn_country_name = self.country.name
        self.dn_city_name = self.city.name

        if self.street and self.house_number:
            self.type = PlaceType.STREET_ADDRESS
        else:
            self.type = PlaceType.POI

        super(Place, self).save(*args, **kwargs)

    def serialize(self):
        return {
            'id': self.id,
            'name': self.name,
            'aliases': self.aliases,
            'description': self.description,
            'city_name': self.dn_city_name,
            'street': self.street,
            'house_number': self.house_number,
            'lon': self.lon,
            'lat': self.lat,
            'country_code': settings.DEFAULT_COUNTRY_CODE
        }