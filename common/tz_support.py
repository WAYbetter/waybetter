'''
tz_support.py

A utility module to handle timezone requirements
'''

import datetime
import time
from django.db import models

class UTC(datetime.tzinfo):
    """UTC"""

    def utcoffset(self, dt):
        return datetime.timedelta(0)

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return datetime.timedelta(0)


class IsraelTimeZone(datetime.tzinfo):
    """
    Israel time zone. UTC+2 and DST
    """

    def utcoffset(self, dt):
        return datetime.timedelta(hours=2) + self.dst(dt)

    def tzname(self, dt):
        return "UTC+2"

    # update this when DST is on/off
    def dst(self, dt):
#        return datetime.timedelta(hours=1) # DST on
        return datetime.timedelta(0)     # DST off

TZ_INFO = {
    "UTC": UTC(),
    "Asia/Jerusalem": IsraelTimeZone()
}

class UTCDateTimeField(models.DateTimeField):
    '''
    A time zone aware DateTime field.

    On read from db converts the naive date to UTC and then to the specified timezone
    One write to db converts the tz aware date to UTC
    '''

    description = "A time zone aware DateTime field"

    __metaclass__ = models.SubfieldBase

    def to_python(self, value):
        '''
        convert the naive date to a tz aware date, uses settings.TIME_ZONE
        for conversion
        '''

        if value is None:
            return None

        value = super(UTCDateTimeField, self).to_python(value)

        if value.tzinfo:
            return value

        if not isinstance(value, datetime.datetime):
            raise ValueError("value '%s' is of type '%s'. should be datetime.datetime" % (value, type(value)))

        return value.replace(tzinfo=TZ_INFO["UTC"]).astimezone(TZ_INFO['Asia/Jerusalem'])

    def get_prep_value(self, value):
        """
        convert a tz aware date into a naive date, after converting to UTC timezone
        """
        if value and hasattr(value, "tzinfo"):

            if value.tzinfo: # make sure this is a tz aware date
                value = value.astimezone(TZ_INFO["UTC"]).replace(tzinfo=None)

        return super(UTCDateTimeField, self).get_prep_value(value)


def utc_now():
    return datetime.datetime.now(TZ_INFO["UTC"])

def default_tz_now():
    return datetime.datetime.now(TZ_INFO["Asia/Jerusalem"])

def default_tz_now_min():
    return datetime.datetime.combine(default_tz_now(), set_default_tz_time(datetime.time.min))

def default_tz_now_max():
    return datetime.datetime.combine(default_tz_now(), set_default_tz_time(datetime.time.max))

def set_default_tz_time(time):
    return time.replace(tzinfo=TZ_INFO["Asia/Jerusalem"])

def to_js_date(dt):
    """
    @param dt: a datetime object
    @return: the date formatted in a Javascript friendly format
    """
    if not dt:
        return None
    elif not dt.tzinfo:
        dt = dt.replace(tzinfo=TZ_INFO["UTC"])
    return time.mktime(dt.astimezone(TZ_INFO["UTC"]).timetuple()) * 1000

def total_seconds(td):
    """
    @param td: a timedelta object
    @return: the total number of seconds contained in the duration
    """
    # TODO_WB: deprecate this when 2.7 is available for GAE
    # timedelta.total_seconds is new in Python 2.7.
    # See: http://docs.python.org/library/datetime.html#datetime.timedelta.total_seconds
    return (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6

def to_task_name_safe(t):
    return t.ctime().replace(":","_").replace(" ","_")

def floor_datetime(dt, minutes=5):
    mod = dt.minute % minutes
    if mod:
        dt -= datetime.timedelta(minutes=mod)

    return dt

def ceil_datetime(dt, minutes=5):
    mod = dt.minute % minutes
    if mod:
        dt += datetime.timedelta(minutes=minutes)
        dt -= datetime.timedelta(minutes=mod)

    return dt