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
        return datetime.timedelta(hours=1) # DST on
        # return timedelta(0)     # DST off

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

def set_default_tz_time(time):
    return time.replace(tzinfo=TZ_INFO["Asia/Jerusalem"])

def to_js_date(dt):
    """
    @param dt: a datetime object
    @return: the date formatted in a Javascript friendly format
    """
    return time.mktime(dt.astimezone(TZ_INFO["UTC"]).timetuple()) * 1000