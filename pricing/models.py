from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext, ugettext_lazy as _
import logging

from common.tz_support import TZ_INFO, UTCDateTimeField
from common.util import DAY_OF_WEEK_CHOICES, FIRST_WEEKDAY, LAST_WEEKDAY, convert_python_weekday, datetimeIterator, Enum
from common.models import BaseModel, CityAreaField
from common.widgets import EditableListField

from linguo.models import MultilingualModel

class TARIFFS(Enum):
    TARIFF1 = 'tariff1'
    TARIFF2 = 'tariff2'

class RuleSet(BaseModel):
    """
    A set of rules having something in common
    """
    name = models.CharField(_("name"), max_length=50)
    station_display_name = models.CharField("name to display in station accounting", max_length=50, null=True, blank=True)
    priority = models.FloatField(_("priority"), unique=True)
    tariff_type = models.CharField(choices=TARIFFS.choices(), max_length=20)

    class Meta:
        ordering = ['-priority']

    def __unicode__(self):
        return self.name

    def is_active(self, dt):
        for rule in self.rules.all():
            if rule.is_active(dt):
                return True

        return False

    @classmethod
    def get_active_set(cls, dt):
        for rule_set in cls.objects.all():
            if rule_set.is_active(dt):
                return rule_set

        return None

class AbstractTemporalRule(BaseModel):
    """
    An abstract base class for temporal rules.
    """
    class Meta:
        abstract = True

    name = models.CharField(_("name"), max_length=50, null=True, blank=True)

    from_date = models.DateField(_("from date"), null=True, blank=True)
    to_date = models.DateField(_("to date"), null=True, blank=True)

    from_weekday = models.IntegerField(_("from day"), choices=DAY_OF_WEEK_CHOICES, null=True, blank=True)
    to_weekday = models.IntegerField(_("to day"), choices=DAY_OF_WEEK_CHOICES, null=True, blank=True)

    from_hour = models.TimeField(_("from hour"))
    to_hour = models.TimeField(_("to hour"))

    def __unicode__(self):
        return self.name

    def clean(self):
        by_date = bool(self.from_date or self.to_date)
        by_weekday = bool(self.from_weekday or self.to_weekday)

        if not (by_date or by_weekday):
            raise ValidationError("Please enter either date or weekday range")

        elif by_date and by_weekday:
            raise ValidationError("Can not define time frame by both date and weekday.")

        elif by_date and not (self.from_date and self.to_date):
            raise ValidationError("Please enter both From and To fields")

        elif by_date and self.from_date > self.to_date:
            raise ValidationError("From date should be earlier than To date")

        elif by_weekday and not (self.from_weekday and self.to_weekday):
            raise ValidationError("Please enter both From and To fields")

        elif self.from_hour > self.to_hour:
            raise ValidationError("Invalid hour range")

    def is_active(self, dt):
        """
        Check if the rule is active on day, or on day and time.
        @param dt: a datetime instance
        @return: True if rule is active, else False
        """
        dt = dt.astimezone(TZ_INFO["Asia/Jerusalem"])

        day = dt.date()
        t = dt.time()

        if self.from_date and self.to_date and self.from_date <= day <= self.to_date:
            return True if t is None else self.from_hour <= t <= self.to_hour
        elif convert_python_weekday(day.weekday()) in self.get_weekdays():
            return True if t is None else self.from_hour <= t <= self.to_hour

        return False

    def get_closest_active(self, dt_target, dt_start, dt_end, delta):

        dt_itr = datetimeIterator(from_datetime=dt_start, to_datetime=dt_end, delta=delta)
        active_dts = []

        for dt in dt_itr:
            if self.is_active(dt):
                active_dts.append(dt)

        if active_dts:
            active_dts = sorted(active_dts, key=lambda dt: abs(dt - dt_target))
            return active_dts[0]

        return None

    def get_dates(self, start_date=None, end_date=None):
        """
        Dates on which the rule is active.
        @param start_date: a datetime.date lower bound.
        @param end_date: a datetime.date upper bound.
        @return: a list of dates.
        """
        dates = []
        if self.from_date and self.to_date:
            if self.from_date == self.to_date and start_date <= self.from_date <= end_date:
                dates = [self.from_date]
            elif self.from_date < self.to_date:
                d1 = max(start_date, self.from_date) if start_date else self.from_date
                d2 = min(end_date, self.to_date) if end_date else self.to_date
                dates = list(datetimeIterator(d1, d2))

        return dates

    def get_weekdays(self):
        """
        Days of week on which the rule is active.
        These are not standard python weekdays, see convert_python_weekday.
        @return: a list of weekdays.
        """
        weekdays = []
        if self.from_weekday and self.to_weekday:
            if self.from_weekday == self.to_weekday:
                weekdays = [self.from_weekday]
            elif self.from_weekday < self.to_weekday:
                weekdays = range(self.from_weekday, self.to_weekday + 1)
            else:
                weekdays = range(self.from_weekday, LAST_WEEKDAY + 1) + range(FIRST_WEEKDAY, self.to_weekday + 1)

        return weekdays


class TemporalRule(AbstractTemporalRule):
    rule_set = models.ForeignKey(RuleSet, verbose_name=_("rule set"), related_name="rules", null=True, blank=True)


class DiscountRule(MultilingualModel, AbstractTemporalRule):
    percent = models.FloatField(_("percent"), null=True, blank=True)
    amount = models.FloatField(_("amount"), null=True, blank=True)
    fixed_price = models.FloatField(_("fixed_price"), null=True, blank=True)

    picture_url = models.URLField(max_length=255, null=True, blank=True, help_text="Will be used as the passenger picture")
    display_name = models.CharField(max_length=25, null=True, blank=True, help_text="Will be used as the passenger name")
    offer_text = models.CharField(max_length=105, null=True, blank=True, help_text="Will be used as the offer text")
    open_to_all = models.BooleanField(default=True, editable=False)

    from_city_area = CityAreaField(verbose_name=_("from city area"), null=True, blank=True, related_name="discount_rules_1")
    from_everywhere = models.BooleanField(verbose_name=_("from everywhere"), default=False)
    from_address = models.CharField(_("from address"), max_length=80, null=True, blank=True)

    to_city_area = CityAreaField(verbose_name=_("to city area"), null=True, blank=True, related_name="discount_rules_2")
    to_everywhere = models.BooleanField(verbose_name=_("to everywhere"), default=False)
    to_address = models.CharField(_("to address"), max_length=80, null=True, blank=True)

    bidi = models.BooleanField(verbose_name=_("bidirectional"), default=False)

    email_domains = EditableListField(models.CharField(max_length=255), null=True, blank=True)

    class Meta:
        # translatable fields
        translate = ('display_name', 'offer_text', 'from_address', 'to_address')

    def clean(self):
        if not (sum([bool(self.percent), bool(self.amount), bool(self.fixed_price)]) == 1):
            raise ValidationError("Only one discount is allowed - percent OR amount OR fixed_price")

        if not (sum([self.from_everywhere, bool(self.from_city_area), bool(self.from_address)]) == 1):
            raise ValidationError("Must choose FROM where the discount is active")

        if not (sum([self.to_everywhere, bool(self.to_city_area), bool(self.to_address)]) == 1):
            raise ValidationError("Must choose TO where the discount is active")

        if not self.picture_url:
            self.picture_url = 'http://www.waybetter.com/static/images/wb_site/1.2/discount_passenger.png'

        if not self.display_name:
            self.display_name = ugettext("*Gift*")

        super(DiscountRule, self).clean()

    def is_active_at(self, dt, pickup_address, dropoff_address):
        """
        @param pickup_address: Address instance
        @param dropoff_address: Address instance
        """
        if not self.is_active(dt):
            return False

        from_address, to_address = pickup_address.formatted_address, dropoff_address.formatted_address
        from_lat, from_lon = pickup_address.lat, pickup_address.lng
        to_lat, to_lon = dropoff_address.lat, dropoff_address.lng

        logging.info("checking if %s is active at %s %s %s" % (self.name, dt, from_address, to_address))

        active_from = self.from_everywhere
        active_to = self.to_everywhere

        from_address_translations = self.get_translations("from_address")
        to_address_translations = self.get_translations("to_address")

        if (not active_from) and self.from_address:
            active_from = from_address in from_address_translations or (self.bidi and to_address in to_address_translations)

        if (not active_to) and self.to_address:
            active_to = to_address in to_address_translations or (self.bidi and from_address in to_address_translations)

        if (not active_from) and self.from_city_area:
            active_from = self.from_city_area.contains(from_lat, from_lon) or (self.bidi and self.from_city_area.contains(to_lat, to_lon))

        if (not active_to) and self.to_city_area:
            active_to = self.to_city_area.contains(to_lat, to_lon) or (self.bidi and self.to_city_area.contains(from_lat, from_lon))

        return active_from and active_to

    def get_discount(self, price):
        round_to = 0.5
        discount = 0

        if self.fixed_price:
            new_price  = min(self.fixed_price, price)
            discount = price - new_price
        elif self.amount:
            discount = min(self.amount, price)  # discount amount must be smaller than price
        elif self.percent:
            discount = self.percent * price / 100

        return discount - (discount % round_to)  # 12.75 -> 12.5


class Promotion(BaseModel):
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255)

    start_dt = UTCDateTimeField()
    end_dt = UTCDateTimeField()
    quota = models.IntegerField(null=True, blank=True)
    discount_rule = models.ForeignKey(DiscountRule, related_name="promotions")

    first_ride_only = models.BooleanField(default=False)
    applies_once = models.BooleanField(default=False)

    description_for_user = models.CharField(max_length=512, help_text=_("what will be displayed in the user's account page"))

    def save(self, *args, **kwargs):
        self.discount_rule.open_to_all = False
        self.discount_rule.save()

        if self.first_ride_only:
            self.applies_once = True

        super(Promotion, self).save(*args, **kwargs)

    def applies_to(self, passenger):
        result = True

        if self.first_ride_only:
            result = passenger.successful_orders.count() == 0
        if self.applies_once:
            result = passenger.successful_orders.filter(promotion=self).count() == 0

        logging.info(u"[Promotion.applies_to] %s = %s" % (self.name, result))
        return result

class PromoCode(BaseModel):
    promotion = models.ForeignKey(Promotion)
    code = models.CharField(max_length=12)