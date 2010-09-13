from django.conf import settings
from common.models import Country
import datetime
from common.util import convert_python_weekday

def estimate_cost(est_duration, est_distance, country_code=settings.DEFAULT_COUNTRY_CODE,
                    cities=None, streets=None, day_of_week=None, time=None,
                    from_address=None, to_address=None):
    """
    Calculates an estimated cost for a ride, based on the estimated duration &amp; distance,
    together with the relevant Pricing Rules defined for the country.
    """

    # Step 1: find the relevant pricing rules
    country = Country.objects.get(code=country_code)
    base_rules = country.pricing_rules.all()
    relevant_rules = filter_relevant_rules(base_rules, cities, streets, day_of_week,
                                             time, from_address, to_address)

    # Step 2: sum up the rules with fixed cost
    total_fixed_cost = sum([rule.fixed_cost for rule in relevant_rules if rule.fixed_cost])

    # Step 3: sum up the cost-by-ticks rules according to distance
    relevant_distance_rules = filter_relevant_distance_rules(relevant_rules, est_distance)
    tick_cost_by_distance = sum([rule.tick_cost * (distance/rule.tick_distance) for distance, rule in relevant_distance_rules])

    # Step 4: sum up the cost-by-ticks rules according to duration
    relevant_duration_rules = filter_relevant_duration_rules(relevant_rules, est_duration)
    tick_cost_by_duration = sum([rule.tick_cost * (duration/rule.tick_time) for duration, rule in relevant_duration_rules])

    # Step 5: choose the maximum between the 2
    max_tick_cost = max(tick_cost_by_distance, tick_cost_by_duration)

    return total_fixed_cost + max_tick_cost




def filter_relevant_rules(base_rules, cities=None, streets=None, day_of_week=None, time=None,
                    from_address=None, to_address=None):
    relevant_rules = []
    for rule in base_rules:
        rule_conditions = {}
        # check special place
        if rule.special_place:
            rule_conditions["special_place"] = False
            for collection in [cities, streets]:
                if collection:
                    if sum([rule.special_place in loc for loc in collection]) > 0:
                        rule_conditions["special_place"] = True
                        break
        # check special city
        if rule.city:
            rule_conditions["city"] = False
            if cities:
                if sum([rule.city in loc for loc in cities]) > 0:
                    rule_conditions["city"] = True
            if sum([rule.city in loc for loc in [from_address, to_address] if loc is not None]) > 0:
                rule_conditions["city"] = True
        # check day of week
        if rule.from_day_of_week and rule.to_day_of_week:
            rule_conditions["day_of_week"] = False
            if day_of_week is None:
                day_of_week = convert_python_weekday(datetime.datetime.now().weekday())
            if rule.from_day_of_week <= day_of_week <= rule.to_day_of_week:
                rule_conditions["day_of_week"] = True
        # check hours range
        if rule.from_hour and rule.to_hour:
            rule_conditions["time"] = False
            if time is None:
                time = datetime.datetime.now().time()
            start_time = datetime.time(rule.from_hour.hour, rule.from_hour.minute)
            end_time = datetime.time(rule.to_hour.hour, rule.to_hour.minute)
            if start_time <= time <= end_time:
                rule_conditions["time"] = True
        if sum([val for key, val in rule_conditions.items()]) == len(rule_conditions):
            relevant_rules.append(rule)
    return relevant_rules


def filter_relevant_distance_rules(base_rules, est_distance):
    """
    Returns a list of (distance, rule) tuples.
    """
    result = []
    for rule in base_rules:
        if rule.from_distance or rule.to_distance:
            if rule.to_distance and est_distance > rule.to_distance:
                d = rule.to_distance - rule.from_distance
                result.append( (d, rule) )
            elif est_distance > rule.from_distance:
                d = est_distance - rule.from_distance
                result.append( (d, rule) )
            else:
                pass
    return result

def filter_relevant_duration_rules(base_rules, est_duration):
    """
    Returns a list of (duration, rule) tuples.
    """
    result = []
    for rule in base_rules:
        if rule.from_duration or rule.to_duration:
            if rule.to_duration and est_duration > rule.to_duration:
                d = rule.to_duration - rule.from_duration
                result.append( (d, rule) )
            elif est_duration > rule.from_duration:
                d = est_duration - rule.from_duration
                result.append( (d, rule) )
            else:
                pass
    return result