from django.db import models
from django.utils.translation import ugettext_lazy as _
from djangotoolbox.fields import ListField
from common.decorators import run_in_transaction
import logging

class BaseModel(models.Model):
    '''
    Adds common methods to our models
    '''
    class Meta:
        abstract = True


    def fresh_copy(self):
        return type(self).by_id(self.id)

    @classmethod
    def by_id(cls, id):
        try:
            obj = cls.objects.get(id=id)
        except cls.DoesNotExist:
            obj = None

        return obj

    @classmethod
    def get_one(cls):
        '''
        Convenience method for getting an instance of this model
        Returns the first instance found
        '''
        if cls.objects.count():
            return cls.objects.all()[0]
        else:
            return None

    @run_in_transaction
    def _change_attr_in_transaction(self, attname, old_value, new_value):
        if old_value == new_value:
            return False
        elif not old_value:
            setattr(self, attname, new_value)
            self.save()
            return True
        elif getattr(self, attname) == old_value:
            setattr(self, attname, new_value)
            self.save()
            return True
        else:
            logging.warning("%s.%s : update in transaction failed" % (self.__class__.__name__, attname))
            return False

class Country(BaseModel):
    name = models.CharField(_("name"), max_length=60, unique=True)
    code = models.CharField(_("country code"), max_length=3, unique=True)
    dial_code = models.CharField(_("dial code"), max_length=6, null=True, blank=True)

    class Meta:
        verbose_name_plural = _("countries")
        ordering = ["name"]

    def __unicode__(self):
        return self.name

    @classmethod
    def get_id_by_code(cls, country_code):
        if not country_code:
            return None

        query = Country.objects.filter(code=country_code)
        if query.count() == 0:
            raise LookupError("No country found matching '%s'" % country_code)

        return query[0].id

    @classmethod
    def country_choices(cls, order_by="name"):
        return [(c.id, "%s (%s)" % (c.name, c.dial_code)) for c in cls.objects.all().order_by(order_by)]


    def save(self, force_insert=False, force_update=False, using=None):
        super(Country, self).save(force_insert, force_update, using)
        self.full_clean()

    def print_all_rules(self):
        rules = []
        for rule in self.metered_rules:
            rules += rule
        for rule in self.extra_charge_rules:
            rules += rule
        for rule in self.flat_rate_rules:
            rules += rule

        return rules

    def delete_all_rules(self):
        self.metered_rules.all().delete()
        self.flat_rate_rules.all().delete()
        self.extra_charge_rules.all().delete()


class City(BaseModel):
    name = models.CharField(_("name"), max_length=50)
    country = models.ForeignKey(Country, verbose_name=_("country"), related_name="cities")
    aliases = ListField(models.CharField(max_length=50))

    class Meta:
    #        fields = ("name", "country", "aliases")
        verbose_name_plural = _("cities")
        ordering = ('name',)

    def __unicode__(self):
        return self.name

    @staticmethod
    def city_choices(country, order_by="name"):
        return [(c.id, c.name) for c in City.objects.filter(country=country).order_by(order_by)]

    @classmethod
    def get_id_by_name_and_country(cls, name, country_id, add_if_not_found=False):
        if not name or not country_id:
            return None

        query = City.objects.filter(name=name, country=country_id)
        if query.count() == 0:
            if add_if_not_found:
                new_city = City()
                new_city.country = Country.objects.get(id=country_id)
                new_city.name = name
                new_city.save()
                return new_city.id
            else:
                raise LookupError("No city found matching '%s, %s'" % (name, country_id))
        else:
            return query[0].id


class CityArea(BaseModel):
    name = models.CharField(_("name"), max_length=50)
    city = models.ForeignKey(City, verbose_name=_("city"), related_name="city_areas")

    def __unicode__(self):
        return self.name