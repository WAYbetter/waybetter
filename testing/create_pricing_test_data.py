# -*- coding: utf-8 -*-

from django.core import serializers

from common.models import Country, City
from ordering.pricing import setup_israel_meter_and_extra_charge_rules
from ordering.rules_controller import add_flat_rate_rule

OUTPUT_FILE = "/home/amir/dev/data/pricing_test_data.yaml"

def create():
    IL = Country.objects.get(code="IL")
    city_a = City.objects.get(name="תל אביב יפו")
    city_b = City.objects.get(name="אור יהודה")

    setup_israel_meter_and_extra_charge_rules()

    IL.flat_rate_rules.all().delete()
    add_flat_rate_rule(country=IL, from_city=city_a, to_city=city_b, fixed_cost_tariff_1=66, fixed_cost_tariff_2=70)

    out = open(OUTPUT_FILE, 'w')

    out.write('# created using create_pricing_data.py\n')

    all_objects = []

    all_objects += list(IL.flat_rate_rules.all())
    all_objects += list(IL.metered_rules.all())
    all_objects += list(IL.extra_charge_rules.all())

    data = serializers.serialize("yaml", all_objects)
    out.write(data)
    out.close()