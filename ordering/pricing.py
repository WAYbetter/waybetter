# -*- coding: utf-8 -*-

from meterCalc import calculate_meter

from django.conf import settings
from django.utils import simplejson
from common.models import Country, City, CityArea
import datetime
from common.util import convert_python_weekday
from ordering.models import PricingRule, SpecificPricingRule
from django.shortcuts import get_object_or_404

# Extras:


def estimate_cost(est_duration, est_distance, country_code=settings.DEFAULT_COUNTRY_CODE, cities=[],
                  day=None, time=None, extras=["Phone order"]):

    if cities is None:
        cities = []
    if day is None:
        day = convert_python_weekday(datetime.datetime.now().weekday()) if day is None else day
    if time is None:
        time = datetime.datetime.now().time()

    # Step 1: flat rate or by meter ?
    flat_rate_rules = []
    if flat_rate(cities):
        city_a = country.cities.get(id=cities[0].id)
        city_b = country.cities.get(id=cities[1].id)

        flat_rate_rules = list(country.flat_rate_rules.filter(city1=city_a, city2=city_b))
        flat_rate_rules += country.flat_rate_rules.filter(city1=city_b, city2=city_a)

        flat_rate_rules = filter_relevant_daytime_rules(flat_rate_rules, day, time)

    if flat_rate_rules != []:
        cost = flat_rate_rules[0].fixed_cost
    else:
        meter_rules = country.metered_rules.all()
        cost = calculate_meter_cost(meter_rules, est_duration, est_distance, day, time)

    # Step 2: add extra costs (airport, phone order etc.)
    extra_charge_rules = [country.extra_charge_rules.filter(rule_name=extra).get() for extra in extras]
    #TODO: don't use rule name for filtering
    extra_cost = sum([rule.cost for rule in extra_charge_rules])

    # return total cost
    return cost + extra_cost


# currently, passing two different cities indicates flat rate
def flat_rate(cities):
    if len(cities) == 2 and cities[0] != cities[1]:
        return True

    return False

def filter_relevant_daytime_rules(rule_list, day, time):
    """
    filter relevant rules at day and time from given list
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


