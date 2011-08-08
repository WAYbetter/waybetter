from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _
from common.util import DAY_OF_WEEK_CHOICES, FIRST_WEEKDAY, LAST_WEEKDAY, convert_python_weekday, datetimeIterator
from common.models import BaseModel


class RuleSet(BaseModel):
    """
    A set of rules having something in common
    """
    name = models.CharField(_("name"), max_length=50)
    priority = models.FloatField(_("priority"), unique=True, null=True, blank=True)

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

        if by_date and by_weekday:
            raise ValidationError("Can not define time frame by both date and weekday.")

        elif by_date and not (self.from_date and self.to_date):
            raise ValidationError("Please enter both From and To fields")

        elif by_date and self.from_date > self.to_date:
            raise ValidationError("From date should be earlier than To date")

        elif by_weekday and not (self.from_weekday and self.to_weekday):
            raise ValidationError("Please enter both From and To fields")

    def is_active(self, day, t=None):
        """
        Check if the rule is active on day, or on day and time.
        @param day: a datetime.date instance
        @param t: a datetime.time instance
        @return: True if rule is active, else False
        """
        if self.from_date and self.to_date and self.from_date <= day <= self.to_date:
            return self.from_hour <= t <= self.to_hour if t else True
        elif convert_python_weekday(day.weekday()) in self.get_weekdays():
            return self.from_hour <= t <= self.to_hour if t else True

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
            if self.from_date == self.to_date:
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