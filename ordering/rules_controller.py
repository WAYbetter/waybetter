# This Python file uses the following encoding: utf-8

import csv
from StringIO import StringIO
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render_to_response
from ordering.forms import SpecificPricingRuleSetupForm
from django.template.context import RequestContext
from django.views.decorators.csrf import csrf_protect
from ordering.pricing import setup_pricing_rules
from common.models import City
from ordering.models import SpecificPricingRule
from datetime import time
import logging
from google.appengine.ext import deferred

# DeadlineExceededError can live in two different places
try:
    # When deployed
    from google.appengine.runtime import DeadlineExceededError
except ImportError:
    from google.appengine.runtime.apiproxy_errors import DeadlineExceededError
    # In the development server

def init_pricing_rules(request):
    if "token" in request.GET:
        if request.GET["token"] == 'waybetter_init':
            setup_pricing_rules()
            return HttpResponse("Done")
        else:
            return HttpResponseForbidden()


def do_setup_specific_pricing_rules(country, data, start=0):
    cache = {}
    result = u""
    i = 0
    try:
        csv_reader = csv.reader(StringIO(data))
        for row in csv_reader:
            if i < start: continue
            from_city = resolve_city(cache, row[0].decode('utf-8'), country)
            to_city = resolve_city(cache, row[1].decode('utf-8'), country)
            fixed_cost1 = float(row[2])
            fixed_cost2 = float(row[3])
            add_specific_rule(country, from_city, to_city, fixed_cost1, fixed_cost2)
            result = u"%s<li>Added rule: %s -> %s" % (result, from_city.name, to_city.name)
            i = i + 1
    except DeadlineExceededError:
        logging.info("deffering after %d specific rules created" % i)
        deferred.defer(do_setup_specific_pricing_rules, country, data, start + i)
    return result

@csrf_protect
# TODO_WB: check authentication
def setup_specific_rules(request):
    if request.method == 'POST':
        form = SpecificPricingRuleSetupForm(request.POST)
        if form.is_valid():
            country = form.cleaned_data["country"]
            # remove existing specific rules
            SpecificPricingRule.objects.filter(country=country).delete()
            data = form.cleaned_data["csv"].encode('utf-8')
            return HttpResponse(do_setup_specific_pricing_rules(country, data))
    else:
        form = SpecificPricingRuleSetupForm()
    return render_to_response("specific_pricing_rules_setup.html", locals(), context_instance=RequestContext(request))



def resolve_city(cache, name, country):
    if name in cache:
        return cache[name]
    else:
        city = City.get_by_name_and_country(name, country.id, True)
        cache[name] = city
        return city


def add_specific_rule(country, from_city, to_city, fixed_cost_tariff_1, fixed_cost_tariff_2):
    # add tariff1 rule
    rule = SpecificPricingRule()
    rule.city = from_city
    rule.to_city = to_city
    rule.fixed_cost = fixed_cost_tariff_1
    rule.country = country
    rule.from_day_of_week = 1
    rule.to_day_of_week = 6
    rule.from_hour = time(5-1, 30-1)
    rule.to_hour = time(21-1, 00)
    rule.save()
    # add tariff2 rule - nights
    rule = SpecificPricingRule()
    rule.city = from_city
    rule.to_city = to_city
    rule.fixed_cost = fixed_cost_tariff_2
    rule.country = country
    rule.from_day_of_week = 1
    rule.to_day_of_week = 6
    rule.from_hour = time(21-1, 30)
    rule.to_hour = time(5-1, 29-1)
    rule.save()
    # add tariff2 rule - weekend
    rule = SpecificPricingRule()
    rule.city = from_city
    rule.to_city = to_city
    rule.fixed_cost = fixed_cost_tariff_2
    rule.country = country
    rule.from_day_of_week = 7
    rule.to_day_of_week = 7
    rule.save()
