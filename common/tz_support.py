'''
tz_support.py

A utility module to handle timezone requirements
'''

import datetime
import logging
import time
import traceback
from django.conf import settings
from django.db import models
from django.utils.dateformat import format as date_format

class UTC(datetime.tzinfo):
    """UTC"""

    def utcoffset(self, dt):
        return datetime.timedelta(0)

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return datetime.timedelta(0)

ISRAEL_DST_SCHEDULE = {
    2010: (datetime.datetime(2010, 3, 26, 2), datetime.datetime(2010, 9, 12, 2)),
    2011: (datetime.datetime(2011, 4, 1, 2), datetime.datetime(2011, 10, 2, 2)),
    2012: (datetime.datetime(2012, 3, 30, 2), datetime.datetime(2012, 9, 23, 2)),
    2013: (datetime.datetime(2013, 3, 29, 2), datetime.datetime(2013, 9, 8, 2)),
    2014: (datetime.datetime(2014, 3, 28, 2), datetime.datetime(2014, 9, 28, 2)),
}

class IsraelTimeZone(datetime.tzinfo):
    """
    Israel time zone. UTC+2 and DST
    """

    def utcoffset(self, dt):
        if not dt:
            return None
        return datetime.timedelta(hours=2) + self.dst(dt)

    def tzname(self, dt):
        return "UTC+2"

    def dst(self, dt):
        _dt = dt.replace(tzinfo=None)
        dst_start, dst_end = ISRAEL_DST_SCHEDULE.get(_dt.year, (None, None))
        if dst_start and dst_end:
            if dst_start <= _dt < dst_end:
                return datetime.timedelta(hours=1)
            else:
                return datetime.timedelta(0)

        if dt.year > 1:
            logging.warning("DST not defined for year %s" % dt.year)

        return datetime.timedelta(0)

TZ_INFO = {
    "UTC": UTC(),
    "Asia/Jerusalem": IsraelTimeZone()
}

TZ_JERUSALEM = TZ_INFO["Asia/Jerusalem"]

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

def normalize_naive_israel_dt(dt):
    """
    @param dt: a naive datetime object in israel time
    @return: a tz aware utc converted datetime
    """
    return dt.replace(tzinfo=TZ_INFO['Asia/Jerusalem']).astimezone(TZ_INFO['UTC'])

def trim_seconds(dt):
    return dt.replace(second=0, microsecond=0)

def default_tz_now():
    return datetime.datetime.now(TZ_INFO["Asia/Jerusalem"])

def default_tz_time_min():
    return set_default_tz_time(datetime.time.min)

def default_tz_time_max():
    return set_default_tz_time(datetime.time.max)

def default_tz_now_min():
    return datetime.datetime.combine(default_tz_now(), set_default_tz_time(datetime.time.min))

def default_tz_now_max():
    return datetime.datetime.combine(default_tz_now(), set_default_tz_time(datetime.time.max))

def set_default_tz_time(dt):
    return dt.replace(tzinfo=TZ_INFO["Asia/Jerusalem"])

def format_dt(dt):
    return date_format(dt, settings.DATETIME_FORMAT)

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

def unix_time(dt):
    """
    returns to number of seconds since 1/1/1970
    @param dt: must be a tz aware datetime
    @return:
    """
    epoch = datetime.datetime.utcfromtimestamp(0).replace(tzinfo=TZ_INFO["UTC"])
    delta = dt.astimezone(TZ_INFO["UTC"]) - epoch
    return total_seconds(delta)


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