import types
from google.appengine.ext import db
from common.errors import TransactionError
from common.tz_support import UTCDateTimeField
from common.util import Polygon
from django.db import models
from django.db.models.fields.related import ManyToOneRel
from django.utils.translation import ugettext_lazy as _
from djangotoolbox.fields import ListField
from common.decorators import run_in_transaction, order_relative_to_field
import logging
from common.widgets import ListFieldWithUI, ColorField, CityAreaFormField

def obj_by_attr(cls, attr_name, attr_val, safe=True):
    if safe and not attr_val:
        return None

    try:
        filter_dict = {attr_name: attr_val}
        obj = cls.objects.get(**filter_dict)
    except cls.DoesNotExist, e:
        if safe:
            obj = None
        else:
            raise e

    return obj

class BaseModel(models.Model):
    create_date = UTCDateTimeField(_("create date"), auto_now_add=True, null=True, blank=True)
    modify_date = UTCDateTimeField(_("modify date"), auto_now=True, null=True, blank=True)

    """
    Adds common methods to our models
    """
    class Meta:
        abstract = True


    def fresh_copy(self):
        return type(self).by_id(self.id)

    @classmethod
    def by_id(cls, id, safe=True):
        return obj_by_attr(cls, "id", id, safe=safe)

    @classmethod
    def get_one(cls):
        """
        Convenience method for getting an instance of this model
        Returns the first instance found


        @param cls:
        @return: the first instance of this class
        """
        try:
            return cls.objects.all()[0]
        except:
            return None

    @run_in_transaction
    def _change_attr_in_transaction(self, attname, old_value=None, new_value=None, safe=True):
        """
        change the given attribute value from B{old_value} to B{new_value}
        
        @param attname: the attribute name to change
        @param old_value: the old value - current value must equal old_value for change to happen
        @param new_value: the new value to set
        @return: True to signal success
        """
        obj = self.fresh_copy()  # ensure we have the latest version of the object
        if old_value == new_value:
            logging.info("old == new")
            result =  False
        elif old_value is None:
            setattr(obj, attname, new_value)
            obj.save()
            result = True
        elif getattr(obj, attname) == old_value:
            setattr(obj, attname, new_value)
            obj.save()
            result = True
        else:
            result = False

        if not result:
            msg = "%s.%s : update in transaction failed (%s --> %s) current=%s" % (self.__class__.__name__, attname, str(old_value), str(new_value), str(getattr(obj, attname)))
            if safe:
                logging.warning(msg)
            else:
                raise TransactionError(msg)
        else:
            logging.info("%s.%s : update in transaction (%s --> %s)" % (self.__class__.__name__, attname, str(old_value), str(new_value)))

        return result

    def __unicode__(self):
        if self.id:
            return u"%s [%d]" % (type(self).__name__, self.id)
        else:
            return u"%s [?]" % (type(self).__name__)

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

class CityAreaField(models.ForeignKey):
    def __init__(self, to_field=None, rel_class=ManyToOneRel, **kwargs):
        super(CityAreaField, self).__init__(CityArea, to_field=to_field, rel_class=rel_class, **kwargs)

    def formfield(self, **kwargs):
        defaults = {
            'form_class': CityAreaFormField,
        }
        defaults.update(kwargs)
        return super(CityAreaField, self).formfield(**defaults)

class CityArea(BaseModel):
    name = models.CharField(_("name"), max_length=50)
    points = ListFieldWithUI(models.FloatField(), verbose_name=_("Edit Points"))
    color = ColorField(default="#ffff00")
    city = models.ForeignKey(City, verbose_name=_("city"), related_name="city_areas")

    def __unicode__(self):
        return self.name

    @property
    def polygon(self):
        return Polygon(self.points)

    def contains(self, lat, lon):
        return self.polygon.contains(lat, lon)
    
CityArea = order_relative_to_field(CityArea, 'city')

class Counter(BaseModel):
    name = models.CharField(max_length=50)
    value = models.IntegerField(default=1)

    @classmethod
    def get_next(cls, name):
        counter, created = cls.objects.get_or_create(name=name)
        def increment(id):
            c = cls.objects.get(id=id)
            c.value += 1
            c.save()
            return c.value

        return db.run_in_transaction(increment, counter.id)

class Message(BaseModel):
    key = models.CharField(help_text="A unique name for this chunk of content", blank=False, max_length=255, unique=True)
    content = models.TextField(blank=True)

    def __unicode__(self):
        return u"%s" % (self.key,)
