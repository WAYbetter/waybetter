# -*- coding: utf-8 -*-

from django.conf import settings
from common.models import Country, City
import datetime
from common.util import convert_python_weekday
from ordering.errors import InvalidRuleSetup
from ordering.models import MeteredRateRule, ExtraChargeRule

# Extras:
PHONE_ORDER = "Phone order"
NATBAG_AIRPORT = "נמל תעופה בן גוריון"
SDE_DOV_AIRPORT = "נמל תעופה שדה דב"
HAIFA_PORT = "נמל חיפה"
KVISH_6 = "כביש 6"

def estimate_cost(est_duration, est_distance, country_code=settings.DEFAULT_COUNTRY_CODE, cities=None,
                  day=None, time=None, extras=None):
    """

    cities = a list of city ids
    """

    # init defaults
    country = Country.objects.get(code=country_code)

    if extras is None:
        extras = []

    if not PHONE_ORDER in extras:
        extras.append(PHONE_ORDER)

    if cities is None:
        cities = []

    if day is None:
        day = convert_python_weekday(datetime.datetime.now().weekday())

    if time is None:
        time = datetime.datetime.now().time()

    # Step 1: flat rate or by meter ?
    flat_rate_rules = []
    if flat_rate(cities):
        city_a = City.objects.get(id=cities[0])
        city_b = City.objects.get(id=cities[1])

        flat_rate_rules = list(country.flat_rate_rules.filter(city1=city_a, city2=city_b))
        flat_rate_rules += country.flat_rate_rules.filter(city1=city_b, city2=city_a)

        flat_rate_rules = filter_relevant_daytime_rules(flat_rate_rules, day, time)

        if len(flat_rate_rules) > 1:
            raise InvalidRuleSetup(
                    "Multiple flat rules for same city pair encountered: %s, %s" % (city_a.name, city_b.name))

    if flat_rate_rules:
        cost = flat_rate_rules[0].fixed_cost
    else:
        cost = calculate_meter_cost(country.metered_rules.all(), est_duration, est_distance, day, time)

    # Step 2: add extra costs (airport, phone order etc.)
    extra_charge_rules = [country.extra_charge_rules.filter(rule_name=extra).get() for extra in extras]
    extra_cost = sum([rule.cost for rule in extra_charge_rules])

    # return total cost
    return cost + extra_cost


# currently, passing two different cities indicates flat rate
def flat_rate(cities):
    return len(cities) == 2 and cities[0] != cities[1]

def filter_relevant_daytime_rules(rule_list, day, time):
    """
    filter relevant rules at day and time from given list
    ---
    rule_list   : list of rules of any type
    day         ; day of week (1-7)
    time        : datetime instance
    """
    result = []
    for rule in rule_list:
        # if rule is day-dependent check if it applies at day
        if rule.from_day and rule.to_day:
            if not (rule.from_day <= day <= rule.to_day):
                continue

        # if rule is time-dependent check if it applies at time
        if rule.from_hour and rule.to_hour:
            start_time = datetime.time(rule.from_hour.hour, rule.from_hour.minute)
            end_time = datetime.time(rule.to_hour.hour, rule.to_hour.minute)
            if start_time < end_time:
                if not (start_time <= time <= end_time):
                    continue
            else:
                # end time is smaller than start time since it is the next day (night fare)
                if not(
                (start_time <= time <= datetime.time(23, 59, 59)) or (datetime.time(00, 00, 00) <= time <= end_time)):
                    continue
        result.append(rule)
    return result

def calculate_meter_cost(rule_list, est_duration, est_distance, day, time):
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
    return total_fixed_cost + max(tick_cost_by_distance, tick_cost_by_duration)

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


def setup_israel_meter_and_extra_charge_rules():
    IL = Country.objects.filter(code="IL").get()

    # meter rules
    TARIFF1_START = datetime.time(05, 30)
    TARIFF1_END = datetime.time(21, 00)
    TARIFF2_START = datetime.time(21, 01)
    TARIFF2_END = datetime.time(05, 29)

    IL.metered_rules.all().delete()
    meter_rules = [
            MeteredRateRule(rule_name="Tariff 1 initial cost", country=IL, from_day=1, to_day=6, from_hour=TARIFF1_START
                            , to_hour=TARIFF1_END, from_duration=0, to_duration=None, from_distance=0, to_distance=None,
                            tick_distance=None, tick_time=None, tick_cost=None, fixed_cost=11.1),
            MeteredRateRule(rule_name="Tariff 2 initial cost", country=IL, from_day=1, to_day=6, from_hour=TARIFF2_START
                            , to_hour=TARIFF2_END, from_duration=0, to_duration=None, from_distance=0, to_distance=None,
                            tick_distance=None, tick_time=None, tick_cost=None, fixed_cost=11.1),

            MeteredRateRule(rule_name="Tariff 1 first 15 km", country=IL, from_day=1, to_day=6, from_hour=TARIFF1_START,
                            to_hour=TARIFF1_END, from_duration=83, to_duration=None, from_distance=559.45,
                            to_distance=15000, tick_distance=90.09, tick_time=12, tick_cost=0.3, fixed_cost=None),
            MeteredRateRule(rule_name="Tariff 2 first 15 km", country=IL, from_day=1, to_day=6, from_hour=TARIFF2_START,
                            to_hour=TARIFF2_END, from_duration=36, to_duration=None, from_distance=153.81,
                            to_distance=15000, tick_distance=72.15, tick_time=10, tick_cost=0.3, fixed_cost=None),

            MeteredRateRule(rule_name="Tariff 1 after 15 km", country=IL, from_day=1, to_day=6, from_hour=TARIFF1_START,
                            to_hour=TARIFF1_END, from_duration=None, to_duration=None, from_distance=15000,
                            to_distance=None, tick_distance=75.14, tick_time=12, tick_cost=0.3, fixed_cost=None),
            MeteredRateRule(rule_name="Tariff 2 after 15 km", country=IL, from_day=1, to_day=6, from_hour=TARIFF2_START,
                            to_hour=TARIFF2_END, from_duration=None, to_duration=None, from_distance=15000,
                            to_distance=None, tick_distance=60.03, tick_time=10, tick_cost=0.3, fixed_cost=None),

            MeteredRateRule(rule_name="Saturday initial cost", country=IL, from_day=7, to_day=7,
                            from_hour=datetime.time(00, 00), to_hour=datetime.time(23, 59), from_duration=0,
                            to_duration=None, from_distance=0, to_distance=None, tick_distance=None, tick_time=None,
                            tick_cost=None, fixed_cost=11.1),
            MeteredRateRule(rule_name="Saturday first 15 km", country=IL, from_day=7, to_day=7,
                            from_hour=datetime.time(00, 00), to_hour=datetime.time(23, 59), from_duration=36,
                            to_duration=None, from_distance=153.81, to_distance=15000, tick_distance=72.15, tick_time=10
                            , tick_cost=0.3, fixed_cost=None),
            MeteredRateRule(rule_name="Saturday after 15 km", country=IL, from_day=7, to_day=7,
                            from_hour=datetime.time(00, 00), to_hour=datetime.time(23, 59), from_duration=None,
                            to_duration=None, from_distance=15000, to_distance=None, tick_distance=60.03, tick_time=10,
                            tick_cost=0.3, fixed_cost=None),
    ]
    for rule in meter_rules: rule.save()

    # Extra charge rules
    IL.extra_charge_rules.all().delete()
    extra_charge_rules = [
            ExtraChargeRule(rule_name=PHONE_ORDER, country=IL, cost=4.5),
            ExtraChargeRule(rule_name=NATBAG_AIRPORT, country=IL, cost=5),
            ExtraChargeRule(rule_name=SDE_DOV_AIRPORT, country=IL, cost=2),
            ExtraChargeRule(rule_name=HAIFA_PORT, country=IL, cost=2),
            ExtraChargeRule(rule_name=KVISH_6, country=IL, cost=14.3),
    ]
    for rule in extra_charge_rules: rule.save()
