from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _
from common.util import DAY_OF_WEEK_CHOICES, FIRST_WEEKDAY, LAST_WEEKDAY, convert_python_weekday, datetimeIterator, Enum
from common.models import BaseModel, CityAreaField

PRIVATE_RIDE_HANDLING_FEE = 0 #NIS

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

    def is_active(self, day, t):
        for rule in self.rules.all():
            if rule.is_active(day, t):
                return True

        return False

    @classmethod
    def get_active_set(cls, day, t):
        for rule_set in cls.objects.all():
            if rule_set.is_active(day, t):
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

    def is_active(self, day, t=None):
        """
        Check if the rule is active on day, or on day and time.
        @param day: a datetime.date instance
        @param t: a datetime.time instance
        @return: True if rule is active, else False
        """
        if self.from_date and self.to_date and self.from_date <= day <= self.to_date:
            return True if t is None else self.from_hour <= t <= self.to_hour
        elif convert_python_weekday(day.weekday()) in self.get_weekdays():
            return True if t is None else self.from_hour <= t <= self.to_hour

        return False


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


class DiscountRule(AbstractTemporalRule):
    percent = models.FloatField(_("percent"), null=True, blank=True)
    amount = models.FloatField(_("amount"), null=True, blank=True)

    from_city_area = CityAreaField(verbose_name=_("from city area"), related_name="fixed_price_rules_1")
    to_city_area = CityAreaField(verbose_name=_("to city area"), related_name="fixed_price_rules_2")

    bidi = models.BooleanField(verbose_name=_("bidirectional"), default=False)

    def clean(self):
        if not (bool(self.percent) ^ bool(self.amount)):
            raise ValidationError("Must set discount percent or amount but not both")

        super(DiscountRule, self).clean()

    def is_active(self, from_lat, from_lon, to_lat, to_lon, day, t):
        contains = self.from_city_area.contains(from_lat, from_lon) and self.to_city_area.contains(to_lat, to_lon)
        if self.bidi:
            contains = contains or (self.from_city_area.contains(to_lat, to_lon) and self.to_city_area.contains(from_lat, from_lon))

        return contains and super(DiscountRule, self).is_active(day, t)

    def get_discount(self, price):
        round_to = 0.5

        if self.amount:
            return min(self.amount, price)  # max discount is the price itself
        elif self.percent:
            discount = self.percent * price / 100
            return discount - (discount % round_to)  # 12.75 -> 12.5