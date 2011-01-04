# -*- coding: utf-8 -*-

from django.conf import settings
from django.utils import simplejson
from common.models import Country, City, CityArea
import datetime
from common.util import convert_python_weekday
from ordering.models import PricingRule, SpecificPricingRule
from django.shortcuts import get_object_or_404

def estimate_cost(est_duration, est_distance, country_code=settings.DEFAULT_COUNTRY_CODE,
                    cities=None, streets=None, day_of_week=None, time=None,
                    from_address=None, to_address=None):
    """
    Calculates an estimated cost for a ride, based on the estimated duration &amp; distance,
    together with the relevant Pricing Rules defined for the country.

    ARGS:
    est_duration: in seconds
    est_distance: in meters
    country_code: country in which this ride is taking place (optional)
    cities: cities that are visited in this ride (optional)
    streets:
    day_of_week:
    time:
    from_address:
    to_address:
    """

    country = Country.objects.get(code=country_code)

    # Step 1: first look for specific rules (inter-city prices)
    if prescreen_specific_rules(cities):
    # ride is between two different cities
        specific_rules = country.specific_pricing_rules.filter(city=cities[0], to_city=cities[1])
#        specific_rules = SpecificPricingRule.objects.filter(country=country, city=cities[0], to_city=cities[1])
        relevant_rules = filter_relevant_specific_rules(specific_rules)
        if relevant_rules != []:
            return relevant_rules[0].fixed_cost

    # Step 2: find the relevant pricing rules
    base_rules = country.pricing_rules.all()
    relevant_rules = filter_relevant_rules(base_rules, cities, streets, day_of_week,
                                             time, from_address, to_address)

    # Step 3: sum up the rules with fixed cost
    total_fixed_cost = sum([rule.fixed_cost for rule in relevant_rules if rule.fixed_cost])

    # Step 4: sum up the cost-by-ticks rules according to distance
    relevant_distance_rules = filter_relevant_distance_rules(relevant_rules, est_distance)
    tick_cost_by_distance = sum([rule.tick_cost * (distance/rule.tick_distance) for distance, rule in relevant_distance_rules])

    # Step 5: sum up the cost-by-ticks rules according to duration
    relevant_duration_rules = filter_relevant_duration_rules(relevant_rules, est_duration)
    tick_cost_by_duration = sum([rule.tick_cost * (duration/rule.tick_time) for duration, rule in relevant_duration_rules])

    # Step 6: choose the maximum between the 2
    max_tick_cost = max(tick_cost_by_distance, tick_cost_by_duration)

    return total_fixed_cost + max_tick_cost




def filter_relevant_rules(base_rules, cities=None, streets=None, day_of_week=None, time=None,
                    from_address=None, to_address=None):
    relevant_rules = []
    if cities:
        city_names = get_city_names(cities)
    else:
        city_names = []
    for rule in base_rules:
        rule_conditions = {}
        # check special place
        if rule.special_place:
            rule_conditions["special_place"] = False
            for collection in [city_names, streets]:
                if collection:
                    if sum([rule.special_place in loc for loc in collection]) > 0:
                        rule_conditions["special_place"] = True
                        break
        # check special city
        if rule.city:
            rule_conditions["city"] = False
            if cities:
                if sum([rule.city.id in cities]) > 0:
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
            if start_time < end_time:
                if start_time <= time <= end_time:
                    rule_conditions["time"] = True
            # night fare, the end time is smaller than the start time since it is the next day
            else:
                if (start_time <= time <= datetime.time(23,59,59)) or (datetime.time(23,59,59)<= time <= end_time):
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
            elif rule.from_duration and est_duration > rule.from_duration:
                d = est_duration - rule.from_duration
                result.append( (d, rule) )
            else:
                pass
    return result



def filter_relevant_specific_rules(specific_rules, day_of_week=None, time=None):
    """
    ARGS:
    specific_rules: list of specific rules between two cities
    day_of_week: that specific rules should apply in
    time: that specific rules should apply at
    """
    result = []
    for rule in specific_rules:
        # if rule is day-dependent check if it applies at day_of_week
        if rule.from_day_of_week and rule.to_day_of_week:
            if day_of_week is None:
                day_of_week = convert_python_weekday(datetime.datetime.now().weekday())
            if not (rule.from_day_of_week <= day_of_week <= rule.to_day_of_week):
                continue
        # if rule is time-dependent check if it applies at time
        if rule.from_hour and rule.to_hour:
            if time is None:
                time = datetime.datetime.now().time()
            start_time = datetime.time(rule.from_hour.hour, rule.from_hour.minute)
            end_time = datetime.time(rule.to_hour.hour, rule.to_hour.minute)
            if not (start_time <= time <= end_time):
                continue
        result.append(rule)
    return result



def prescreen_specific_rules(cities):
    if cities:
        if len(cities) == 2:
            if cities[0] != cities[1]:
                return True
    return False


def get_city_names(cities):
    result = []
    for id in cities:
        city = get_object_or_404(City, id=id)
        result.append(city.name)
    return result


ISRAELI_RULES = """
[
    {
        "pk": 334,
        "model": "ordering.pricingrule",
        "fields": {"create_date": "2010-09-12 13:44:37", "from_distance": null, "to_day_of_week": null, "city": null, "state": "", "city_area": null, "to_duration": null, "fixed_cost": 4.5, "is_active": true, "rule_name": "Phone order", "from_day_of_week": null, "to_hour": null, "vehicle_type": null, "tick_time": null, "tick_distance": null, "tick_cost": null, "country": 2, "special_place": null, "from_hour": null, "modify_date": "2010-09-12 13:44:37", "to_distance": null, "from_duration": null}
    },
    {
        "pk": 335,
        "model": "ordering.pricingrule",
        "fields": {"create_date": "2010-09-12 13:44:37", "from_distance": null, "to_day_of_week": 6, "city": null, "state": "", "city_area": null, "to_duration": null, "fixed_cost": 11.1, "is_active": true, "rule_name": "Tariff 1 - initial cost", "from_day_of_week": 1, "to_hour": "21:00:00", "vehicle_type": null, "tick_time": null, "tick_distance": null, "tick_cost": null, "country": 2, "special_place": null, "from_hour": "05:30:00", "modify_date": "2010-09-12 15:58:41", "to_distance": null, "from_duration": null}
    },
    {
        "pk": 336,
        "model": "ordering.pricingrule",
        "fields": {"create_date": "2010-09-12 13:44:37", "from_distance": null, "to_day_of_week": 6, "city": "אילת", "state": "", "city_area": null, "to_duration": null, "fixed_cost": 9.5, "is_active": true, "rule_name": "Tariff 1 - initial cost - Eilat", "from_day_of_week": 1, "to_hour": "21:00:00", "vehicle_type": null, "tick_time": null, "tick_distance": null, "tick_cost": null, "country": 2, "special_place": null, "from_hour": "05:30:00", "modify_date": "2010-09-12 15:58:41", "to_distance": null, "from_duration": null}
    },
    {
        "pk": 354,
        "model": "ordering.pricingrule",
        "fields": {"create_date": "2010-09-12 15:58:41", "from_distance": 559.45000000000005, "to_day_of_week": 6, "city": null, "state": "", "city_area": null, "to_duration": null, "fixed_cost": null, "is_active": true, "rule_name": "Tariff 1 - cost in 1st 15KM", "from_day_of_week": 1, "to_hour": "21:00:00", "vehicle_type": null, "tick_time": 12, "tick_distance": 90.090000000000003, "tick_cost": 0.29999999999999999, "country": 2, "special_place": null, "from_hour": "05:30:00", "modify_date": "2010-09-12 17:26:51", "to_distance": 15000.0, "from_duration": 83}
    },
    {
        "pk": 355,
        "model": "ordering.pricingrule",
        "fields": {"create_date": "2010-09-12 15:58:41", "from_distance": 559.79, "to_day_of_week": 6, "city": "אילת", "state": "", "city_area": null, "to_duration": null, "fixed_cost": null, "is_active": true, "rule_name": "Tariff 1 - cost in 1st 15KM - Eilat", "from_day_of_week": 1, "to_hour": "21:00:00", "vehicle_type": null, "tick_time": 15, "tick_distance": 105.52, "tick_cost": 0.29999999999999999, "country": 2, "special_place": null, "from_hour": "05:30:00", "modify_date": "2010-09-12 17:26:51", "to_distance": 15000.0, "from_duration": 83}
    },
    {
        "pk": 357,
        "model": "ordering.pricingrule",
        "fields": {"create_date": "2010-09-12 16:49:13", "from_distance": 15000.0, "to_day_of_week": 6, "city": null, "state": "", "city_area": null, "to_duration": null, "fixed_cost": null, "is_active": true, "rule_name": "Tariff 1 - cost after 15KM", "from_day_of_week": 1, "to_hour": "21:00:00", "vehicle_type": null, "tick_time": 12, "tick_distance": 75.140000000000001, "tick_cost": 0.29999999999999999, "country": 2, "special_place": null, "from_hour": "05:30:00", "modify_date": "2010-09-12 19:20:04", "to_distance": null, "from_duration": null}
    },
    {
        "pk": 358,
        "model": "ordering.pricingrule",
        "fields": {"create_date": "2010-09-12 16:49:13", "from_distance": 15000.0, "to_day_of_week": 6, "city": "אילת", "state": "", "city_area": null, "to_duration": null, "fixed_cost": null, "is_active": true, "rule_name": "Tariff 1 - cost after 15KM - Eilat", "from_day_of_week": 1, "to_hour": "21:00:00", "vehicle_type": null, "tick_time": 15, "tick_distance": 84.519999999999996, "tick_cost": 0.29999999999999999, "country": 2, "special_place": null, "from_hour": "05:30:00", "modify_date": "2010-09-12 19:20:04", "to_distance": null, "from_duration": null}
    },
    {
        "pk": 361,
        "model": "ordering.pricingrule",
        "fields": {"create_date": "2010-09-12 19:20:04", "from_distance": null, "to_day_of_week": 6, "city": null, "state": "", "city_area": null, "to_duration": null, "fixed_cost": 11.1, "is_active": true, "rule_name": "Tariff 2 - initial cost", "from_day_of_week": 1, "to_hour": "05:29:00", "vehicle_type": null, "tick_time": null, "tick_distance": null, "tick_cost": null, "country": 2, "special_place": null, "from_hour": "21:01:00", "modify_date": "2010-09-12 19:20:04", "to_distance": null, "from_duration": null}
    },
    {
        "pk": 362,
        "model": "ordering.pricingrule",
        "fields": {"create_date": "2010-09-12 19:20:04", "from_distance": null, "to_day_of_week": 6, "city": "אילת", "state": "", "city_area": null, "to_duration": null, "fixed_cost": 9.5, "is_active": true, "rule_name": "Tariff 2 - initial cost - Eilat", "from_day_of_week": 1, "to_hour": "05:29:00", "vehicle_type": null, "tick_time": null, "tick_distance": null, "tick_cost": null, "country": 2, "special_place": null, "from_hour": "21:01:00", "modify_date": "2010-09-12 19:20:04", "to_distance": null, "from_duration": null}
    },
    {
        "pk": 364,
        "model": "ordering.pricingrule",
        "fields": {"create_date": "2010-09-12 17:26:51", "from_distance": 153.81, "to_day_of_week": 6, "city": null, "state": "", "city_area": null, "to_duration": null, "fixed_cost": null, "is_active": true, "rule_name": "Tariff 2 - cost in 1st 15KM", "from_day_of_week": 1, "to_hour": "05:29:00", "vehicle_type": null, "tick_time": 10, "tick_distance": 72.150000000000006, "tick_cost": 0.29999999999999999, "country": 2, "special_place": null, "from_hour": "21:01:00", "modify_date": "2010-09-12 17:26:51", "to_distance": 15000.0, "from_duration": 36}
    },
    {
        "pk": 365,
        "model": "ordering.pricingrule",
        "fields": {"create_date": "2010-09-12 17:26:51", "from_distance": 154.16999999999999, "to_day_of_week": 6, "city": "אילת", "state": "", "city_area": null, "to_duration": null, "fixed_cost": null, "is_active": true, "rule_name": "Tariff 2 - cost in 1st 15KM - Eilat", "from_day_of_week": 1, "to_hour": "05:29:00", "vehicle_type": null, "tick_time": 12, "tick_distance": 84.420000000000002, "tick_cost": 0.29999999999999999, "country": 2, "special_place": null, "from_hour": "21:01:00", "modify_date": "2010-09-12 17:26:51", "to_distance": 15000.0, "from_duration": 36}
    },
    {
        "pk": 369,
        "model": "ordering.pricingrule",
        "fields": {"create_date": "2010-09-12 17:30:21", "from_distance": 15000.0, "to_day_of_week": 6, "city": null, "state": "", "city_area": null, "to_duration": null, "fixed_cost": null, "is_active": true, "rule_name": "Tariff 2 - cost after 15KM", "from_day_of_week": 1, "to_hour": "05:29:00", "vehicle_type": null, "tick_time": 10, "tick_distance": 60.030000000000001, "tick_cost": 0.29999999999999999, "country": 2, "special_place": null, "from_hour": "21:01:00", "modify_date": "2010-09-12 17:30:21", "to_distance": null, "from_duration": null}
    },
    {
        "pk": 370,
        "model": "ordering.pricingrule",
        "fields": {"create_date": "2010-09-12 17:30:21", "from_distance": 15000.0, "to_day_of_week": 6, "city": "אילת", "state": "", "city_area": null, "to_duration": null, "fixed_cost": null, "is_active": true, "rule_name": "Tariff 2 - cost after 15KM - Eilat", "from_day_of_week": 1, "to_hour": "05:29:00", "vehicle_type": null, "tick_time": 12, "tick_distance": 67.590000000000003, "tick_cost": 0.29999999999999999, "country": 2, "special_place": null, "from_hour": "21:00:00", "modify_date": "2010-09-12 17:30:21", "to_distance": null, "from_duration": null}
    },
    {
        "pk": 372,
        "model": "ordering.pricingrule",
        "fields": {"create_date": "2010-09-12 17:35:14", "from_distance": null, "to_day_of_week": 7, "city": null, "state": "", "city_area": null, "to_duration": null, "fixed_cost": 11.1, "is_active": true, "rule_name": "Tariff 2 - Weekend - initial cost", "from_day_of_week": 7, "to_hour": null, "vehicle_type": null, "tick_time": null, "tick_distance": null, "tick_cost": null, "country": 2, "special_place": null, "from_hour": null, "modify_date": "2010-09-12 17:35:14", "to_distance": null, "from_duration": null}
    },
    {
        "pk": 373,
        "model": "ordering.pricingrule",
        "fields": {"create_date": "2010-09-12 17:35:14", "from_distance": null, "to_day_of_week": 7, "city": "אילת", "state": "", "city_area": null, "to_duration": null, "fixed_cost": 9.5, "is_active": true, "rule_name": "Tariff 2 - Weekend - initial cost - Eilat", "from_day_of_week": 7, "to_hour": null, "vehicle_type": null, "tick_time": null, "tick_distance": null, "tick_cost": null, "country": 2, "special_place": null, "from_hour": null, "modify_date": "2010-09-12 17:35:14", "to_distance": null, "from_duration": null}
    },
    {
        "pk": 374,
        "model": "ordering.pricingrule",
        "fields": {"create_date": "2010-09-12 17:35:14", "from_distance": 153.81, "to_day_of_week": 7, "city": null, "state": "", "city_area": null, "to_duration": null, "fixed_cost": null, "is_active": true, "rule_name": "Tariff 2 - Saturday - cost in 1st 15KM", "from_day_of_week": 7, "to_hour": null, "vehicle_type": null, "tick_time": 10, "tick_distance": 72.150000000000006, "tick_cost": 0.29999999999999999, "country": 2, "special_place": null, "from_hour": null, "modify_date": "2010-09-12 17:35:14", "to_distance": 15000.0, "from_duration": 36}
    },
    {
        "pk": 375,
        "model": "ordering.pricingrule",
        "fields": {"create_date": "2010-09-12 17:35:14", "from_distance": 154.16999999999999, "to_day_of_week": 7, "city": "אילת", "state": "", "city_area": null, "to_duration": null, "fixed_cost": null, "is_active": true, "rule_name": "Tariff 2 - Saturday - cost in 1st 15KM - Eilat", "from_day_of_week": 7, "to_hour": null, "vehicle_type": null, "tick_time": 12, "tick_distance": 84.420000000000002, "tick_cost": 0.29999999999999999, "country": 2, "special_place": null, "from_hour": null, "modify_date": "2010-09-12 17:35:14", "to_distance": 15000.0, "from_duration": 36}
    },
    {
        "pk": 377,
        "model": "ordering.pricingrule",
        "fields": {"create_date": "2010-09-12 17:37:25", "from_distance": 15000.0, "to_day_of_week": 7, "city": null, "state": "", "city_area": null, "to_duration": null, "fixed_cost": null, "is_active": true, "rule_name": "Tariff 2 - Saturday - cost after 15KM", "from_day_of_week": 7, "to_hour": null, "vehicle_type": null, "tick_time": 10, "tick_distance": 60.030000000000001, "tick_cost": 0.29999999999999999, "country": 2, "special_place": null, "from_hour": null, "modify_date": "2010-09-12 17:37:25", "to_distance": null, "from_duration": null}
    },
    {
        "pk": 378,
        "model": "ordering.pricingrule",
        "fields": {"create_date": "2010-09-12 17:37:25", "from_distance": 15000.0, "to_day_of_week": 7, "city": "אילת", "state": "", "city_area": null, "to_duration": null, "fixed_cost": null, "is_active": true, "rule_name": "Tariff 2 - Saturday - cost after 15KM - Eilat", "from_day_of_week": 7, "to_hour": null, "vehicle_type": null, "tick_time": 12, "tick_distance": 67.590000000000003, "tick_cost": 0.29999999999999999, "country": 2, "special_place": null, "from_hour": null, "modify_date": "2010-09-12 17:37:25", "to_distance": null, "from_duration": null}
    },
    {
        "pk": 380,
        "model": "ordering.pricingrule",
        "fields": {"create_date": "2010-09-12 17:41:48", "from_distance": null, "to_day_of_week": null, "city": null, "state": "", "city_area": null, "to_duration": null, "fixed_cost": 14.300000000000001, "is_active": true, "rule_name": "Freeway 6", "from_day_of_week": null, "to_hour": null, "vehicle_type": null, "tick_time": null, "tick_distance": null, "tick_cost": null, "country": 2, "special_place": "\u05db\u05d1\u05d9\u05e9 6", "from_hour": null, "modify_date": "2010-09-13 09:00:01", "to_distance": null, "from_duration": null}
    },
    {
        "pk": 382,
        "model": "ordering.pricingrule",
        "fields": {"create_date": "2010-09-12 17:43:38", "from_distance": null, "to_day_of_week": null, "city": null, "state": "", "city_area": null, "to_duration": null, "fixed_cost": 5.0, "is_active": true, "rule_name": "Ben-Gurion Airport", "from_day_of_week": null, "to_hour": null, "vehicle_type": null, "tick_time": null, "tick_distance": null, "tick_cost": null, "country": 2, "special_place": "\u05e0\u05ea\u05d1\u05d2", "from_hour": null, "modify_date": "2010-09-13 09:00:01", "to_distance": null, "from_duration": null}
    },
    {
        "pk": 383,
        "model": "ordering.pricingrule",
        "fields": {"create_date": "2010-09-12 17:43:38", "from_distance": null, "to_day_of_week": null, "city": null, "state": "", "city_area": null, "to_duration": null, "fixed_cost": 2.0, "is_active": true, "rule_name": "Sde-Dov Airport", "from_day_of_week": null, "to_hour": null, "vehicle_type": null, "tick_time": null, "tick_distance": null, "tick_cost": null, "country": 2, "special_place": "\u05e9\u05d3\u05d4-\u05d3\u05d1", "from_hour": null, "modify_date": "2010-09-13 09:00:01", "to_distance": null, "from_duration": null}
    },
    {
        "pk": 384,
        "model": "ordering.pricingrule",
        "fields": {"create_date": "2010-09-12 17:43:38", "from_distance": null, "to_day_of_week": null, "city": null, "state": "", "city_area": null, "to_duration": null, "fixed_cost": 2.0, "is_active": true, "rule_name": "Haifa Port", "from_day_of_week": null, "to_hour": null, "vehicle_type": null, "tick_time": null, "tick_distance": null, "tick_cost": null, "country": 2, "special_place": "\u05e0\u05de\u05dc \u05d7\u05d9\u05e4\u05d4", "from_hour": null, "modify_date": "2010-09-13 09:00:01", "to_distance": null, "from_duration": null}
    }
]
"""

PRICING_RULES_DATA = {"IL": ISRAELI_RULES}


def setup_pricing_rules():
    for country_code, json in PRICING_RULES_DATA.items():
        country = Country.objects.get(code=country_code)
        rules = simplejson.loads(json)
        for rule in rules:
            fields = rule["fields"]
            pr = PricingRule()
            pr.rule_name = fields["rule_name"]
            pr.is_active = fields["is_active"]
            pr.country = country
            pr.state = fields["state"]
            if fields["city"]: pr.city = City.objects.get(name=fields["city"])
            if fields["city_area"]: pr.city_area = CityArea.objects.get(id=fields["city_area"])
            pr.special_place = fields["special_place"]
            pr.from_hour = fields["from_hour"]
            pr.to_hour = fields["to_hour"]
            pr.from_day_of_week = fields["from_day_of_week"]
            pr.to_day_of_week = fields["to_day_of_week"]
            pr.vehicle_type = fields["vehicle_type"]
            pr.from_distance = fields["from_distance"]
            pr.to_distance = fields["to_distance"]
            pr.from_duration = fields["from_duration"]
            pr.to_duration = fields["to_duration"]
            pr.fixed_cost = fields["fixed_cost"]
            pr.tick_distance = fields["tick_distance"]
            pr.tick_time = fields["tick_time"]
            pr.tick_cost = fields["tick_cost"]
            pr.save()
