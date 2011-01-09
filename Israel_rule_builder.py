# -*- coding: utf-8 -*-

from common.models import *
from ordering.models import *
import datetime

IL = Country.objects.filter(code="IL").get()

# meter rules
TARIFF1_START = datetime.time(05,30)
TARIFF1_END = datetime.time(21,00)
TARIFF2_START = datetime.time(21,01)
TARIFF2_END = datetime.time(05,29)

IL.metered_rules.all().delete()
meter_rules=[
        MeteredRateRule(rule_name="Tariff 1 initial cost",country=IL,from_day=1, to_day=6, from_hour=TARIFF1_START, to_hour=TARIFF1_END, from_duration=0, to_duration=None, from_distance=0, to_distance=None, tick_distance=None, tick_time=None, tick_cost=None, fixed_cost=11.1),
        MeteredRateRule(rule_name="Tariff 2 initial cost",country=IL,from_day=1, to_day=6, from_hour=TARIFF2_START, to_hour=TARIFF2_END, from_duration=0, to_duration=None, from_distance=0, to_distance=None, tick_distance=None, tick_time=None, tick_cost=None, fixed_cost=11.1),

        MeteredRateRule(rule_name="Tariff 1 first 15 km",country=IL,from_day=1, to_day=6, from_hour=TARIFF1_START, to_hour=TARIFF1_END, from_duration=83, to_duration=None, from_distance=559.45, to_distance=15000, tick_distance=90.09, tick_time=12, tick_cost=0.3, fixed_cost=None),
        MeteredRateRule(rule_name="Tariff 2 first 15 km",country=IL,from_day=1, to_day=6, from_hour=TARIFF2_START, to_hour=TARIFF2_END, from_duration=36, to_duration=None, from_distance=153.81, to_distance=15000, tick_distance=72.15, tick_time=10, tick_cost=0.3, fixed_cost=None),

        MeteredRateRule(rule_name="Tariff 1 after 15 km",country=IL,from_day=1, to_day=6, from_hour=TARIFF1_START, to_hour=TARIFF1_END, from_duration=None, to_duration=None, from_distance=15000, to_distance=None, tick_distance=75.14, tick_time=12, tick_cost=0.3, fixed_cost=None),
        MeteredRateRule(rule_name="Tariff 2 after 15 km",country=IL,from_day=1, to_day=6, from_hour=TARIFF2_START, to_hour=TARIFF2_END, from_duration=None, to_duration=None, from_distance=15000, to_distance=None, tick_distance=60.03, tick_time=10, tick_cost=0.3, fixed_cost=None),

        MeteredRateRule(rule_name="Saturday initial cost",country=IL,from_day=7, to_day=7, from_hour=datetime.time(00,00), to_hour=datetime.time(23,59), from_duration=0, to_duration=None, from_distance=0, to_distance=None, tick_distance=None, tick_time=None, tick_cost=None, fixed_cost=11.1),
        MeteredRateRule(rule_name="Saturday first 15 km",country=IL,from_day=7, to_day=7, from_hour=datetime.time(00,00), to_hour=datetime.time(23,59), from_duration=36, to_duration=None, from_distance=153.81, to_distance=15000, tick_distance=72.15, tick_time=10, tick_cost=0.3, fixed_cost=None),
        MeteredRateRule(rule_name="Saturday after 15 km",country=IL,from_day=7, to_day=7, from_hour=datetime.time(00,00), to_hour=datetime.time(23,59), from_duration=None, to_duration=None, from_distance=15000, to_distance=None, tick_distance=60.03, tick_time=10, tick_cost=0.3, fixed_cost=None),
]
for rule in meter_rules: rule.save()


# flat rate rules
IL.flat_rate_rules.all().delete()
city_a = IL.cities.filter(id=1604).get()
city_b = IL.cities.filter(id=1744).get()

flat_rate_rules=[
        FlatRateRule(rule_name="תל אביב, אור יהודה תעריף 1", country=IL, city1=city_a, city2=city_b, fixed_cost=66, from_hour=datetime.time(05, 30), to_hour=datetime.time(21, 00), from_day=1, to_day=6),
        FlatRateRule(rule_name="תל אביב, אור יהודהתעריף 2", country=IL, city1=city_a, city2=city_b, fixed_cost=69, from_hour=datetime.time(21, 01), to_hour=datetime.time(05, 29), from_day=1, to_day=6),
        FlatRateRule(rule_name="תל אביב, אור יהודה שבת", country=IL, city1=city_a, city2=city_b, fixed_cost=69, from_day=7, to_day=7),
]
for rule in flat_rate_rules: rule.save()

# Extra charge rules
IL.extra_charge_rules.all().delete()
extra_charge_rules=[
        ExtraChargeRule(rule_name="Phone order",country=IL,cost="4.5"),
        ExtraChargeRule(rule_name="בן גוריון",country=IL,cost="5")
]
for rule in extra_charge_rules: rule.save()
