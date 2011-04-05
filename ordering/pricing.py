# -*- coding: utf-8 -*-
import logging
import datetime
from datetime import tzinfo, timedelta

from django.conf import settings
from common.models import Country, City
from common.util import convert_python_weekday, Enum
from ordering.errors import InvalidRuleSetup
from ordering.models import MeteredRateRule, ExtraChargeRule

class CostType(Enum):
    METER  = "METER"
    FLAT   = "FLAT"

# Extras:
class IsraelExtraCosts(Enum):
    PHONE_ORDER     = u"Phone order"
    NATBAG_AIRPORT  = u"נמל תעופה בן גוריון"
    SDE_DOV_AIRPORT = u"נמל תעופה שדה דב"
    HAIFA_PORT      = u"נמל חיפה"
    KVISH_6         = u"כביש 6"

class IsraelTimeZone(tzinfo):
    """
    Israel time zone. UTC+2 and DST
    """

    def utcoffset(self, dt):
        return timedelta(hours=2) + self.dst(dt)

    def tzname(self, dt):
        return "UTC+2"

    # update this when DST is on/off
    def dst(self, dt):
        return timedelta(hours=1) # DST on
        # return timedelta(0)     # DST off

ILtz = IsraelTimeZone()

def estimate_cost(est_duration, est_distance, country_code=settings.DEFAULT_COUNTRY_CODE, cities=None,
                  day=None, time=None, extras=None):
    """
    Calculate estimated cost for a taxi ride by meter (by estimated time and duration) or a flat rate.
    Returns a (cost, type) tuple.
    
    cities : a list of city ids. Should contain exactly two different cities.
    day    : day of ride (1-7)
    time   : datetime.time of ride
    extras : a list of extra costs to add. Phone order is automatically added to all rides.
    """

    # init defaults
    country = Country.objects.get(code=country_code)

    if extras is None:
        extras = []

    if not IsraelExtraCosts.PHONE_ORDER in extras:
        extras.append(IsraelExtraCosts.PHONE_ORDER)

    if cities is None:
        cities = []

    if day is None:
        day = convert_python_weekday(datetime.datetime.now().weekday())

    if time is None:
        time = datetime.datetime.now(ILtz).time()

    logging.debug("Calculating estimated cost with (duration, distance, day, time) = (%d. %d, %d, %s)" % (est_duration,est_distance, day, time))

    # Step 1: flat rate or by meter ?
    flat_rate_rules = []
    if flat_rate(cities):
        city_a = City.objects.get(id=cities[0])
        city_b = City.objects.get(id=cities[1])

        flat_rate_rules = list(country.flat_rate_rules.filter(city1=city_a, city2=city_b))
        flat_rate_rules.extend(list(country.flat_rate_rules.filter(city1=city_b, city2=city_a)))

        flat_rate_rules = filter_relevant_daytime_rules(flat_rate_rules, day, time)

        if len(flat_rate_rules) > 1:
            raise InvalidRuleSetup("Multiple flat rules for same city pair encountered: %s, %s" % (city_a.name, city_b.name))

    if flat_rate_rules:
        type = CostType.FLAT
        cost = flat_rate_rules.pop().fixed_cost
    else:
        type = CostType.METER
        cost = calculate_meter_cost(country.metered_rules.all(), est_duration, est_distance, day, time)

    # Step 2: add extra costs (airport, etc.). Phone order is always added
    extra_charge_rules = [country.extra_charge_rules.filter(rule_name=extra).get() for extra in extras]
    extra_cost = sum([rule.cost for rule in extra_charge_rules])

    # return total cost
    logging.debug(u"Estimation %s cost: %d" % (type, cost + extra_cost))
    return cost + extra_cost, type


# currently, passing two different cities indicates flat rate
def flat_rate(cities):
    return len(cities) == 2 and cities[0] != cities[1]

def filter_relevant_daytime_rules(rule_list, day, time):
    """
    filter relevant rules at day and time from given list
    ---
    rule_list: list of rules of any type
    day      : day of ride (1-7)
    time     : datetime.time of ride
    """
    result = []
    for rule in rule_list:
        # if rule is day-dependent check if it applies at day
        if rule.from_day and rule.to_day:
            if not (rule.from_day <= day <= rule.to_day):
                continue
                # if rule is time-dependent check if it applies at time
        if rule.from_hour and rule.to_hour:
            start_time = rule.from_hour
            end_time = rule.to_hour
            if start_time < end_time:
                if not (start_time <= time <= end_time):
                    continue
            else:
                # end time is smaller than start time since it is the next day (night fare)
                if not(
                (start_time <= time <= MIDNIGHT) or (datetime.time(00, 00, 00) <= time <= end_time)):
                    continue
        result.append(rule)
    return result

def calculate_meter_cost(rule_list, est_duration, est_distance, day, time):
    """
    calculate an estimated meter cost based on estimated duration and distance.
    ---
    rule_list: list of MeteredRateRule
    day      : day of ride (1-7)
    time     : datetime.time of ride
    """
    relevant_rules = filter_relevant_daytime_rules(rule_list, day, time)

    total_fixed_cost = sum([rule.fixed_cost for rule in relevant_rules if rule.fixed_cost])

    # sum up the cost-by-ticks rules according to distance
    relevant_distance_rules = filter_relevant_distance_rules(relevant_rules, est_distance)
    tick_cost_by_distance = sum(
            [rule.tick_cost * (distance / rule.tick_distance) for distance, rule in relevant_distance_rules])

    # sum up the cost-by-ticks rules according to duration
    relevant_duration_rules = filter_relevant_duration_rules(relevant_rules, est_duration)
    tick_cost_by_duration = sum(
            [rule.tick_cost * (duration / rule.tick_time) for duration, rule in relevant_duration_rules])

    # choose the maximum between the 2
    return total_fixed_cost+max(tick_cost_by_distance, tick_cost_by_duration)

def filter_relevant_distance_rules(rule_list, est_distance):
    """
    Returns a list of (distance, rule) tuples.
    """
    result = []
    for rule in rule_list:
        if rule.from_distance or rule.to_distance:
            if rule.to_distance and est_distance > rule.to_distance:
                d = rule.to_distance - rule.from_distance
                result.append((d, rule))
            elif est_distance > rule.from_distance:
                d = est_distance - rule.from_distance
                result.append((d, rule))
            else:
                pass
    return result

def filter_relevant_duration_rules(rule_list, est_duration):
    """
    Returns a list of (duration, rule) tuples.
    """
    result = []
    for rule in rule_list:
        if rule.from_duration or rule.to_duration:
            if rule.to_duration and est_duration > rule.to_duration:
                d = rule.to_duration - rule.from_duration
                result.append((d, rule))
            elif rule.from_duration and est_duration > rule.from_duration:
                d = est_duration - rule.from_duration
                result.append((d, rule))
            else:
                pass
    return result


TARIFF1_START = datetime.time(05,30,00)
TARIFF1_END = datetime.time(20,59,59, 999999)
TARIFF2_START = datetime.time(21,00,00)
TARIFF2_END = datetime.time(05,29,59,999999)
MIDNIGHT = datetime.time(23,59,59,999999)
SABBATH_START = datetime.time(17,00,00,000000)
SABBATH_START_MINUS_EPSILON = datetime.time(16,59,59,999999)
tariff1_dict = {
    'BASE_PRICE'              : 11.1, # in NIS
    'BASE_TIME'               : 80, # in sec
    'BASE_DISTANCE'           : 537.93, # in meter
    'TICK_TIME_BELOW_15K'     : 12, # in sec
    'TICK_DISTANCE_BELOW_15K' : 86.63, # in meter
    'TICK_COST_BELOW_15K'     : 0.3, # in NIS
    'TICK_TIME_OVER_15K'      : 12, # in sec
    'TICK_DISTANCE_OVER_15K'  : 72.25, # in meter
    'TICK_COST_OVER_15K'      : 0.3, # in NIS
    }
tariff2_dict = {
    'BASE_PRICE'              : 11.1, # in NIS
    'BASE_TIME'               : 35, # in sec
    'BASE_DISTANCE'           : 147.89, # in meter
    'TICK_TIME_BELOW_15K'     : 10, # in sec
    'TICK_DISTANCE_BELOW_15K' : 69.38, # in meter
    'TICK_COST_BELOW_15K'     : 0.3, # in NIS
    'TICK_TIME_OVER_15K'      : 10, # in sec
    'TICK_DISTANCE_OVER_15K'  : 57.72, # in meter
    'TICK_COST_OVER_15K'      : 0.3, # in NIS
    }
def setup_israel_meter_and_extra_charge_rules():

    IL = Country.objects.filter(code="IL").get()

    # meter rules
    IL.metered_rules.all().delete()
    meter_rules=[
            # Weekdays
            MeteredRateRule(rule_name="Tariff 1 initial cost",country=IL,from_day=1, to_day=5, from_hour=TARIFF1_START, to_hour=TARIFF1_END, from_duration=0, to_duration=None, from_distance=0, to_distance=None, tick_distance=None, tick_time=None, tick_cost=None, fixed_cost=tariff1_dict['BASE_PRICE']),
            MeteredRateRule(rule_name="Tariff 2 initial cost",country=IL,from_day=1, to_day=5, from_hour=TARIFF2_START, to_hour=TARIFF2_END, from_duration=0, to_duration=None, from_distance=0, to_distance=None, tick_distance=None, tick_time=None, tick_cost=None, fixed_cost=tariff2_dict['BASE_PRICE']),

            MeteredRateRule(rule_name="Tariff 1 first 15 km",country=IL,from_day=1, to_day=5, from_hour=TARIFF1_START, to_hour=TARIFF1_END, from_duration=tariff1_dict['BASE_TIME'], to_duration=None, from_distance=tariff1_dict['BASE_DISTANCE'], to_distance=15000, tick_distance=tariff1_dict['TICK_DISTANCE_BELOW_15K'], tick_time=tariff1_dict['TICK_TIME_BELOW_15K'], tick_cost=tariff1_dict['TICK_COST_BELOW_15K'], fixed_cost=None),
            MeteredRateRule(rule_name="Tariff 2 first 15 km",country=IL,from_day=1, to_day=5, from_hour=TARIFF2_START, to_hour=TARIFF2_END, from_duration=tariff2_dict['BASE_TIME'], to_duration=None, from_distance=tariff2_dict['BASE_DISTANCE'], to_distance=15000, tick_distance=tariff2_dict['TICK_DISTANCE_BELOW_15K'], tick_time=tariff2_dict['TICK_TIME_BELOW_15K'], tick_cost=tariff2_dict['TICK_COST_BELOW_15K'], fixed_cost=None),

            MeteredRateRule(rule_name="Tariff 1 after 15 km",country=IL,from_day=1, to_day=5, from_hour=TARIFF1_START, to_hour=TARIFF1_END, from_duration=None, to_duration=None, from_distance=15000, to_distance=None, tick_distance=tariff1_dict['TICK_DISTANCE_OVER_15K'], tick_time=tariff1_dict['TICK_TIME_OVER_15K'], tick_cost=tariff1_dict['TICK_COST_OVER_15K'], fixed_cost=None),
            MeteredRateRule(rule_name="Tariff 2 after 15 km",country=IL,from_day=1, to_day=5, from_hour=TARIFF2_START, to_hour=TARIFF2_END, from_duration=None, to_duration=None, from_distance=15000, to_distance=None, tick_distance=tariff2_dict['TICK_DISTANCE_OVER_15K'], tick_time=tariff2_dict['TICK_TIME_OVER_15K'], tick_cost=tariff2_dict['TICK_COST_OVER_15K'], fixed_cost=None),

            # Friday is a special case of a week day because of SABBATH
            MeteredRateRule(rule_name="Friday Tariff 1 initial cost",country=IL,from_day=6, to_day=6, from_hour=TARIFF1_START, to_hour=SABBATH_START_MINUS_EPSILON, from_duration=0, to_duration=None, from_distance=0, to_distance=None, tick_distance=None, tick_time=None, tick_cost=None, fixed_cost=tariff1_dict['BASE_PRICE']),
            MeteredRateRule(rule_name="Friday Tariff 2 initial cost",country=IL,from_day=6, to_day=6, from_hour=SABBATH_START, to_hour=MIDNIGHT,                    from_duration=0, to_duration=None, from_distance=0, to_distance=None, tick_distance=None, tick_time=None, tick_cost=None, fixed_cost=tariff2_dict['BASE_PRICE']),

            MeteredRateRule(rule_name="Friday Tariff 1 first 15 km",country=IL,from_day=6, to_day=6, from_hour=TARIFF1_START, to_hour=SABBATH_START_MINUS_EPSILON, from_duration=tariff1_dict['BASE_TIME'], to_duration=None, from_distance=tariff1_dict['BASE_DISTANCE'], to_distance=15000, tick_distance=tariff1_dict['TICK_DISTANCE_BELOW_15K'], tick_time=tariff1_dict['TICK_TIME_BELOW_15K'], tick_cost=tariff1_dict['TICK_COST_BELOW_15K'], fixed_cost=None),
            MeteredRateRule(rule_name="Friday Tariff 2 first 15 km",country=IL,from_day=6, to_day=6, from_hour=SABBATH_START, to_hour=MIDNIGHT,                    from_duration=tariff2_dict['BASE_TIME'], to_duration=None, from_distance=tariff2_dict['BASE_DISTANCE'], to_distance=15000, tick_distance=tariff2_dict['TICK_DISTANCE_BELOW_15K'], tick_time=tariff2_dict['TICK_TIME_BELOW_15K'], tick_cost=tariff2_dict['TICK_COST_BELOW_15K'], fixed_cost=None),

            MeteredRateRule(rule_name="Friday Tariff 1 after 15 km",country=IL,from_day=6, to_day=6, from_hour=TARIFF1_START, to_hour=SABBATH_START_MINUS_EPSILON, from_duration=None, to_duration=None, from_distance=15000, to_distance=None, tick_distance=tariff1_dict['TICK_DISTANCE_OVER_15K'], tick_time=tariff1_dict['TICK_TIME_OVER_15K'], tick_cost=tariff1_dict['TICK_COST_OVER_15K'], fixed_cost=None),
            MeteredRateRule(rule_name="Friday Tariff 2 after 15 km",country=IL,from_day=6, to_day=6, from_hour=SABBATH_START, to_hour=MIDNIGHT,                    from_duration=None, to_duration=None, from_distance=15000, to_distance=None, tick_distance=tariff2_dict['TICK_DISTANCE_OVER_15K'], tick_time=tariff2_dict['TICK_TIME_OVER_15K'], tick_cost=tariff2_dict['TICK_COST_OVER_15K'], fixed_cost=None),

            # Saturday
            MeteredRateRule(rule_name="Saturday initial cost",country=IL,from_day=7, to_day=7, from_hour=datetime.time(00,00,00), to_hour=MIDNIGHT, from_duration=0, to_duration=None, from_distance=0, to_distance=None, tick_distance=None, tick_time=None, tick_cost=None, fixed_cost=tariff2_dict['BASE_PRICE']),
            MeteredRateRule(rule_name="Saturday first 15 km",country=IL,from_day=7, to_day=7, from_hour=datetime.time(00,00,00), to_hour=MIDNIGHT, from_duration=tariff2_dict['BASE_TIME'], to_duration=None, from_distance=tariff2_dict['BASE_DISTANCE'], to_distance=15000, tick_distance=tariff2_dict['TICK_DISTANCE_BELOW_15K'], tick_time=tariff2_dict['TICK_TIME_BELOW_15K'], tick_cost=tariff2_dict['TICK_COST_BELOW_15K'], fixed_cost=None),
            MeteredRateRule(rule_name="Saturday after 15 km",country=IL,from_day=7, to_day=7, from_hour=datetime.time(00,00,00), to_hour=MIDNIGHT, from_duration=None,                      to_duration=None, from_distance=15000,                         to_distance=None,  tick_distance=tariff2_dict['TICK_DISTANCE_OVER_15K'],  tick_time=tariff2_dict['TICK_TIME_OVER_15K'],  tick_cost=tariff2_dict['TICK_COST_OVER_15K'], fixed_cost=None),
    ]
    for rule in meter_rules: rule.save()

    # extra charge rules
    IL.extra_charge_rules.all().delete()
    extra_charge_rules=[
            ExtraChargeRule(rule_name=IsraelExtraCosts.PHONE_ORDER,country=IL,cost=4.7),
            ExtraChargeRule(rule_name=IsraelExtraCosts.NATBAG_AIRPORT,country=IL,cost=5),
            ExtraChargeRule(rule_name=IsraelExtraCosts.SDE_DOV_AIRPORT,country=IL,cost=2),
            ExtraChargeRule(rule_name=IsraelExtraCosts.HAIFA_PORT,country=IL,cost=2),
            ExtraChargeRule(rule_name=IsraelExtraCosts.KVISH_6,country=IL,cost=15.1),
    ]
    for rule in extra_charge_rules: rule.save()

    # flat rate rules are set in ordering.rules_controller.setup_flat_rate_rules
