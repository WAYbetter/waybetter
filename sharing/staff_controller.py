from billing.models import BillingTransaction
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.utils import simplejson
from django.utils.translation import get_language_from_request
from django.shortcuts import render_to_response, get_object_or_404
from django.template.context import RequestContext
from common.tz_support import  default_tz_now, set_default_tz_time
from djangotoolbox.http import JSONResponse
from ordering.decorators import passenger_required
from ordering.forms import OrderForm
from ordering.models import StopType, RideComputation, RideComputationSet
from sharing.forms import ConstraintsForm
from sharing.models import HotSpot
from sharing.passenger_controller import HIDDEN_FIELDS
from sharing.algo_api import submit_orders_for_ride_calculation
from datetime import  datetime, date
import time
import settings
import re

POINT_ID_REGEXPT = re.compile("^(p\d+)_")

@staff_member_required
@passenger_required
def hotspot_ordering_page(request, passenger, is_textinput):
    if request.method == 'POST':
        response = ''
        hotspot_type_raw = request.POST.get("hotspot_type", None)

        if hotspot_type_raw in ["pickup", "dropoff"]:
            hotspot_type, point_type = ("from", "to") if hotspot_type_raw == "pickup" else ("to", "from")
            data = request.POST.copy()
            data['passenger'] = passenger
            orders = create_orders_from_hotspot(data, hotspot_type, point_type, is_textinput)

            if orders:
                params = {}
                if float(request.POST.get("time_const_frac") or 0):
                    params["toleration_factor"] = request.POST["time_const_frac"]
                if int(request.POST.get("time_const_min") or 0):
                    params["toleration_factor_minutes"] = request.POST["time_const_min"]
                name = request.POST.get("computation_set_name")
                res = submit_test_computation(orders, params=params, computation_set_name=name)
                response = u"Orders submitted for calculation: %s" % res.content
            else:
                response = "Hotspot data corrupt: no orders created"
        else:
            response = "Hotspot type invalid"

        return HttpResponse(response)

    else: # GET
        is_popup = True
        page_specific_class = "hotspot_page"
        hidden_fields = HIDDEN_FIELDS

        hotspots = [{'name': hotspot.name, 'id': hotspot.id, 'lon': hotspot.lon, 'lat': hotspot.lat}
        for hotspot in HotSpot.objects.all()]

        telmap_user = settings.TELMAP_API_USER
        telmap_password = settings.TELMAP_API_PASSWORD
        telmap_languages = 'he' if str(get_language_from_request(request)) == 'he' else 'en'
        country_code = settings.DEFAULT_COUNTRY_CODE

        constraints_form = ConstraintsForm()

        if is_textinput:
            page_specific_class = "%s textinput" % page_specific_class
            hotspot_times = sorted(map(lambda i: "%d:00" % i, range(0, 24)) +
                                   map(lambda i: "%d:30" % i, range(0, 24)),
                                   key=lambda v: int(v.split(":")[0])) # sorry about that :)
            return render_to_response('hotspot_ordering_page_textinput.html', locals(),
                                      context_instance=RequestContext(request))
        else:
            return render_to_response('hotspot_ordering_page.html', locals(), context_instance=RequestContext(request))


@staff_member_required
def ride_computation_stat(request, computation_set_id):
    computation_set = get_object_or_404(RideComputationSet, id=computation_set_id)
    orders = computation_set.orders

    if request.method == 'POST':
        params = {}
        if float(request.POST.get("time_const_frac") or 0):
            params["toleration_factor"] = request.POST["time_const_frac"]
        if int(request.POST.get("time_const_min") or 0):
            params["toleration_factor_minutes"] = request.POST["time_const_min"]

        res = submit_test_computation(orders, params=params, computation_set_id=computation_set.id)
        return JSONResponse({'content': u"Orders submitted for calculation: %s" % res.content})

    else:
        is_popup = True
        telmap_user = settings.TELMAP_API_USER
        telmap_password = settings.TELMAP_API_PASSWORD
        telmap_languages = 'he'
        pickup = StopType.PICKUP
        dropoff = StopType.DROPOFF
        constrains_form = ConstraintsForm()

        points = set([order.pickup_point for order in orders] + [order.dropoff_point for order in orders])
        points = simplejson.dumps([{'id': p.id, 'lat': p.lat, 'lon': p.lon, 'address': p.address, 'type': p.type}
            for p in sorted(points, key=lambda p: p.stop_time)])

        computations = [{'id': c.id,
                         'stat': simplejson.loads(c.statistics),
                         'toleration_factor': c.toleration_factor,
                         'toleration_factor_minutes': c.toleration_factor_minutes} for c in computation_set.members.filter(completed=True)]

        return render_to_response('ride_computation_stat.html', locals(), context_instance=RequestContext(request))


def create_orders_from_hotspot(data, hotspot_type, point_type, is_textinput):
    fields = ["raw"] + HIDDEN_FIELDS

    if is_textinput:
        hotspot_data = {}
        for f in fields:
            hotspot_data["%s_%s" % (hotspot_type, f)] = data.get("hotspot_%s" % f, None)
        hotspot_datetime = datetime.combine(default_tz_now().date(),
                                            datetime.strptime(data.get("hotspot_time"), "%H:%M").time())
        hotspot_datetime = set_default_tz_time(hotspot_datetime)

    else:
        hotspot = HotSpot.by_id(data.get("hotspot_id"))
        hotspot_data = hotspot.serialize_for_order(hotspot_type)
        hotspot_time = datetime.strptime(data.get("hotspot_time"), "%H:%M").time()
        hotspot_date = date(*time.strptime(data.get("hotspot_date"), '%d/%m/%Y')[:3])
        hotspot_datetime = set_default_tz_time(datetime.combine(hotspot_date, hotspot_time))

    orders = []
    if all(hotspot_data.values()) and hotspot_datetime:
        p_names = []
        for f in data.keys():
            p_name = re.search(POINT_ID_REGEXPT, f)
            if p_name and p_name.groups()[0] not in p_names:
                p_names.append(p_name.groups()[0])

        points = []
        for p_name in p_names:
            p_data = {}
            for f in fields:
                p_data["%s_%s" % (point_type, f)] = data.get("%s_%s" % (p_name, f), None)

            if all(p_data.values()):
                points.append(p_data)

        for p_data in points:
            form_data = p_data.copy()
            form_data.update(hotspot_data)
            form = OrderForm(form_data)
            if form.is_valid():
                order = form.save(commit=False)
                price = None
                if hotspot_type == "from":
                    order.depart_time = hotspot_datetime
                    price = hotspot.get_price(order.to_lat, order.to_lon, hotspot_datetime.date(), hotspot_datetime.time())
                else:
                    order.arrive_time = hotspot_datetime
                    price = hotspot.get_price(order.from_lat, order.from_lon, hotspot_datetime.date(), hotspot_datetime.time())

                passenger = data['passenger']
                order.passenger = passenger
                order.confining_station = passenger.default_sharing_station
                order.save()

                if price and passenger.billing_info:
                    billing_trx = BillingTransaction(order=order, amount=price)
                    billing_trx.save()
                    billing_trx.commit()
                    
                orders.append(order)

    return orders


def submit_test_computation(orders, params, computation_set_name=None, computation_set_id=None):

    key = "test_%s" % str(default_tz_now())
    params.update({'debug': True})
    response = submit_orders_for_ride_calculation(orders, key=key, params=params)

    if response.content:
        algo_key = response.content.strip()
        computation = RideComputation(algo_key=algo_key)
        computation.toleration_factor = params.get('toleration_factor')
        computation.toleration_factor_minutes = params.get('toleration_factor_minutes')

        if computation_set_id: # add to existing set
            computation_set = RideComputationSet.by_id(computation_set_id)
            computation.set = computation_set
        elif computation_set_name: # create new set
            computation_set = RideComputationSet(name=computation_set_name)
            computation_set.save()
            computation.set = computation_set

        computation.save()

        for order in orders:
            order.computation = computation
            order.save()

    return response