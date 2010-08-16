from django.db import models
from django.utils.translation import gettext_lazy as _
                               
# Create your models here.
class Country(models.Model):
    name = models.CharField(_("name"), max_length=60, unique=True)
    code = models.CharField(_("country code"), max_length=3, unique=True)
    dial_code = models.CharField(_("dial code"), max_length=6, null=True, blank=True)

    class Meta:
        verbose_name_plural = _("countries")

    def __unicode__(self):
        return self.name

    @classmethod
    def get_id_by_code(cls, country_code):
        query = Country.objects.filter(code=country_code)
        if query.count() == 0:
            raise LookupError("No country found matching '%s'" % country_code)
        
        return query[0].id

    def save(self, force_insert=False, force_update=False, using=None):
        super(Country, self).save(force_insert, force_update, using)
        self.full_clean()


class City(models.Model):
    name = models.CharField(_("name"), max_length=50)
    country = models.ForeignKey(Country, verbose_name=_("country"), related_name="cities")

    def __unicode__(self):
        return self.name

    @classmethod
    def get_id_by_name_and_country(cls, name, country_id, add_if_not_found=False):
        query = City.objects.filter(name = name, country = country_id)
        if query.count() == 0:
            if add_if_not_found:
                new_city = City()
                new_city.country = Country.objects.get(id = country_id)
                new_city.name = name
                new_city.save()
                return new_city.id
            else:
                raise LookupError("No city found matching '%s, %s'" % (name, country_id))
        else:
            return query[0].id



class CityArea(models.Model):
    name = models.CharField(_("name"), max_length=50)
    city = models.ForeignKey(City, verbose_name=_("city"), related_name="city_areas")

    def __unicode__(self):
        return self.name