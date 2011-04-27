# This Python file uses the following encoding: utf-8

import csv
import datetime
from StringIO import StringIO
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render_to_response
from django.core.urlresolvers import reverse
from ordering.forms import FlatRateRuleSetupForm
from django.template.context import RequestContext
from django.views.decorators.csrf import csrf_protect, csrf_exempt


from ordering.pricing import setup_israel_meter_and_extra_charge_rules
from common.decorators import internal_task_on_queue
from common.models import City, Country
from common.util import get_unique_id
from ordering.models import FlatRateRule

import logging
from google.appengine.api import taskqueue
from google.appengine.api import memcache

import ordering



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
            setup_israel_meter_and_extra_charge_rules()
            return HttpResponse("Done")
        else:
            return HttpResponseForbidden()


def flat_rate_async(country_id, memcache_key, start=0):
    task = taskqueue.Task(url=reverse(do_setup_flat_rate_pricing_rules), params=
        {"country_id": country_id, "memcache_key" : memcache_key, "start": start})
    
    q = taskqueue.Queue('flat-rate-setup')
    q.add(task)

@csrf_exempt
@internal_task_on_queue("flat-rate-setup")
def do_setup_flat_rate_pricing_rules(request):
    country_id  = int(request.POST["country_id"])
    memcache_key = request.POST["memcache_key"]
    start = int(request.POST["start"])

    country = Country.objects.get(id=country_id)

    # remove existing specific rules, this takes some time, but not long enough to get a DeadlineExceededError
    logging.info("Deleting existing rules...")
    FlatRateRule.objects.filter(country=country).delete()
    logging.info("Deleted.")

    cache = {} 
    result = u""
    i = 0
    try:
        data = memcache.get(memcache_key)
        csv_reader = csv.reader(StringIO(data))
        for row in csv_reader:
            if i < start:
                i += 1
                continue

            logging.info("Processing data line %d" % i)
            from_city = resolve_city(cache, row[0].decode('utf-8'), country)
            to_city = resolve_city(cache, row[1].decode('utf-8'), country)
            fixed_cost1 = float(row[2])
            fixed_cost2 = float(row[3])
            add_flat_rate_rule(country, from_city, to_city, fixed_cost1, fixed_cost2)
            result = u"%s<li>Added rule: %s -> %s" % (result, from_city.name, to_city.name)
            i += 1

    except DeadlineExceededError:
        logging.info("deffering after %d specific rules created" % i)
        flat_rate_async(country_id, memcache_key, i)

    return HttpResponse(result)

@csrf_protect
# TODO_WB: check authentication
def setup_flat_rate_rules(request):
    if request.method == 'POST':
        form = FlatRateRuleSetupForm(request.POST)
        if form.is_valid():
            logging.info("Uploading flat rate pricing rules...")
            country = form.cleaned_data["country"]
            data = form.cleaned_data["csv"].encode('utf-8')
            memcache_key = get_unique_id()
            memcache.set(memcache_key, data)
            logging.info("Read data")
            flat_rate_async(country.id, memcache_key)
            return HttpResponse("OK")
    else:
        form = FlatRateRuleSetupForm()
    return render_to_response("flat_rate_rules_setup.html", locals(), context_instance=RequestContext(request))


def resolve_city(cache, name, country):
    if name in cache:
        return cache[name]
    else:
        city_id = City.get_id_by_name_and_country(name, country.id, True)
        city = City.objects.get(id=city_id)
        cache[name] = city
        return city


def add_flat_rate_rule(country, from_city, to_city, fixed_cost_tariff_1, fixed_cost_tariff_2):
    # Weekdays
    rule = FlatRateRule(rule_name="%s -> %s" % (from_city.name, to_city.name), city1=from_city, city2=to_city, country=country)
    rule.from_day = 1
    rule.to_day = 5
    rule.fixed_cost = fixed_cost_tariff_1
    rule.from_hour = ordering.pricing.TARIFF1_START
    rule.to_hour = ordering.pricing.TARIFF1_END
    rule.save()

    rule = FlatRateRule(rule_name="%s -> %s" % (from_city.name, to_city.name), city1=from_city, city2=to_city, country=country)
    rule.from_day = 1
    rule.to_day = 5
    rule.fixed_cost = fixed_cost_tariff_2
    rule.from_hour = ordering.pricing.TARIFF2_START
    rule.to_hour = ordering.pricing.TARIFF2_END
    rule.save()

    # Friday
    rule = FlatRateRule(rule_name="%s -> %s" % (from_city.name, to_city.name), city1=from_city, city2=to_city, country=country)
    rule.from_day = 6
    rule.to_day = 6
    rule.fixed_cost = fixed_cost_tariff_1
    rule.from_hour = ordering.pricing.TARIFF1_START
    rule.to_hour = ordering.pricing.SABBATH_START_MINUS_EPSILON
    rule.save()

    rule = FlatRateRule(rule_name="%s -> %s" % (from_city.name, to_city.name), city1=from_city, city2=to_city, country=country)
    rule.from_day = 6
    rule.to_day = 6
    rule.fixed_cost = fixed_cost_tariff_2
    rule.from_hour = ordering.pricing.SABBATH_START
    rule.to_hour = ordering.pricing.MIDNIGHT
    rule.save()

    # Saturday
    rule = FlatRateRule(rule_name="%s -> %s" % (from_city.name, to_city.name), city1=from_city, city2=to_city, country=country)
    rule.fixed_cost = fixed_cost_tariff_2
    rule.from_day = 7
    rule.to_day = 7
    rule.from_hour = datetime.time(00,00,00)
    rule.to_hour = ordering.pricing.MIDNIGHT
    rule.save()