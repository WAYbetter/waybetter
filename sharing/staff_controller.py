# This Python file uses the following encoding: utf-8
import logging
from billing.enums import BillingStatus
from billing.models import BillingTransaction, BillingInfo
from common.decorators import force_lang
from common.models import City
from common.util import custom_render_to_response
from common.views import base_datepicker_page
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.utils import simplejson, translation
from django.utils.translation import get_language_from_request
from django.shortcuts import render_to_response, get_object_or_404
from django.template.context import RequestContext
from common.tz_support import  default_tz_now, set_default_tz_time, default_tz_now_min, default_tz_now_max
from djangotoolbox.http import JSONResponse
from ordering.decorators import passenger_required
from ordering.forms import OrderForm
from ordering.models import StopType, RideComputation, RideComputationSet, OrderType, RideComputationStatus, ORDER_STATUS, Order, CHARGED, ACCEPTED, APPROVED, REJECTED, TIMED_OUT, FAILED, Passenger, SharedRide
from sharing.forms import ConstraintsForm
from sharing.models import HotSpot
from sharing.passenger_controller import HIDDEN_FIELDS
from sharing.algo_api import submit_orders_for_ride_calculation
from datetime import  datetime, date, timedelta
import time
import settings
import re

POINT_ID_REGEXPT = re.compile("^(p\d+)_")
LANG_CODE = "he"

@staff_member_required
@force_lang("en")
def kpi(request):
    na = "N/A"
    init_start_date = default_tz_now_max() - timedelta(days=7)
    init_end_date = default_tz_now_min()

    def f(start_date, end_date):
        all_orders = list(Order.objects.filter(create_date__gte=start_date, create_date__lte=end_date))
        all_orders = filter(lambda o: not o.debug and o.status in [APPROVED, CHARGED, ACCEPTED, REJECTED, TIMED_OUT, FAILED], all_orders)
        new_passengers = list(Passenger.objects.filter(create_date__gte=start_date, create_date__lte=end_date))
        shared_rides = filter(lambda sr: not sr.debug, SharedRide.objects.filter(create_date__gte=start_date, create_date__lte=end_date))
        shared_rides_with_sharing = filter(lambda sr: sr.stops > 1, shared_rides)
        logging.info("shared_rides (%d): %s" % (len(shared_rides), shared_rides))
        logging.info("shared_rides_with_sharing (%d): %s" % (len(shared_rides_with_sharing), shared_rides_with_sharing))

        all_trx = filter(lambda bt: not bt.debug, BillingTransaction.objects.filter(status=BillingStatus.CHARGED, charge_date__gte=start_date, charge_date__lte=end_date))

        pickmeapp_orders = filter(lambda o: not bool(o.price), all_orders)
        sharing_orders = filter(lambda o: bool(o.price), all_orders)
        accepted_orders = filter(lambda o: o.status == ACCEPTED, pickmeapp_orders)
        pickmeapp_site = filter(lambda o: not o.mobile, pickmeapp_orders)
        pickmeapp_mobile = filter(lambda o: o.mobile, pickmeapp_orders)
        pickmeapp_native = filter(lambda o: o.user_agent.startswith("PickMeApp"), pickmeapp_orders)

        sharing_site = filter(lambda o: not o.mobile, sharing_orders)
        sharing_mobile = filter(lambda o: o.mobile, sharing_orders)
        sharing_native = filter(lambda o: o.user_agent.startswith("WAYbetter"), sharing_orders)

        data = {
            "rides_booked": len(all_orders),
            "sharging_rides": len(sharing_orders),
            "sharing_site_rides": len(sharing_site),
            "sharing_mobile_rides": len(sharing_mobile),
            "sharing_native_rides": len(sharing_native),
            "sharing_site_rides_percent": round(float(len(sharing_site))/len(sharing_orders) * 100, 2) if sharing_orders else "NA",
            "sharing_mobile_rides_percent": round(float(len(sharing_mobile))/len(sharing_orders) * 100, 2) if sharing_orders else "NA",
            "sharing_native_rides_percent": round(float(len(sharing_native))/len(sharing_orders) * 100, 2) if sharing_orders else "NA",
            "pickmeapp_rides": len(pickmeapp_orders),
            "accepted_pickmeapp_rides": round(float(len(accepted_orders))/len(pickmeapp_orders) * 100, 2) if pickmeapp_orders else "NA",
            "pickmeapp_site_rides": len(pickmeapp_site),
            "pickmeapp_mobile_rides": len(pickmeapp_mobile),
            "pickmeapp_native_rides": len(pickmeapp_native),
            "pickmeapp_site_rides_percent": round(float(len(pickmeapp_site))/len(pickmeapp_orders) * 100, 2) if pickmeapp_orders else "NA",
            "pickmeapp_mobile_rides_percent": round(float(len(pickmeapp_mobile))/len(pickmeapp_orders) * 100, 2) if pickmeapp_orders else "NA",
            "pickmeapp_native_rides_percent": round(float(len(pickmeapp_native))/len(pickmeapp_orders) * 100, 2) if pickmeapp_orders else "NA",
            "all_users": Passenger.objects.count(),
            "new_users": len(new_passengers),
            "new_credit_card_users": len(filter(lambda p: hasattr(p, "billing_info"), new_passengers)),
            "all_credit_card_users": BillingInfo.objects.count(),
            "average_sharing": round(float(len(shared_rides_with_sharing)) / len(shared_rides) * 100, 2) if shared_rides else "No Shared Rides",
            "income": round(sum([bt.amount for bt in all_trx]), 2),
            "expenses": sum([sr.value for sr in shared_rides])
        }

        return data

    return base_datepicker_page(request, f, 'kpi.html', locals(), init_start_date, init_end_date)


@staff_member_required
def birdseye_view(request):
    na = "N/A"
    init_start_date = default_tz_now_min()
    init_end_date = default_tz_now_max() + timedelta(days=7)
    order_status_labels = [label for (key, label) in ORDER_STATUS]

    def f(start_date, end_date):
        departing = RideComputation.objects.filter(hotspot_depart_time__gte=start_date,
                                                   hotspot_depart_time__lte=end_date)
        arriving = RideComputation.objects.filter(hotspot_arrive_time__gte=start_date,
                                                  hotspot_arrive_time__lte=end_date)
        data = []

        for c in sorted(list(departing) + list(arriving), key=lambda c: c.hotspot_depart_time or c.hotspot_arrive_time,
                        reverse=True):
            time = c.hotspot_depart_time or c.hotspot_arrive_time
            orders_data = [{'id': o.id,
                            'from': o.from_raw,
                            'to': o.to_raw,
                            'passenger_name': "%s %s" % (o.passenger.user.first_name,
                                                         o.passenger.user.last_name) if o.passenger and o.passenger.user else na
                ,
                            'passenger_phone': o.passenger.phone if o.passenger else na,
                            'type': OrderType.get_name(o.type),
                            'status': o.get_status_label(),
                            'debug': 'debug' if o.debug else ''
            }
            for o in c.orders.all()]

            c_data = {'id': c.id,
                      'status': RideComputationStatus.get_name(c.status),
                      'time': time.strftime("%d/%m/%y, %H:%M"),
                      'dir': 'Hotspot->' if c.hotspot_depart_time else '->Hotspot' if c.hotspot_arrive_time else na,
                      'orders': orders_data,
                      }

            data.append(c_data)
        return data

    return base_datepicker_page(request, f, 'birdseye_view.html', locals(), init_start_date, init_end_date)


@staff_member_required
def staff_home(request):
    page_specific_class = "wb_home staff_home"
    hidden_fields = HIDDEN_FIELDS

    order_types = simplejson.dumps({'private': OrderType.PRIVATE,
                                    'shared': OrderType.SHARED})

    country_code = settings.DEFAULT_COUNTRY_CODE

    cities = [{'id': city.id, 'name': city.name} for city in City.objects.filter(name="תל אביב יפו")]

    is_debug = True

    return custom_render_to_response('wb_home.html', locals(), context_instance=RequestContext(request))


@staff_member_required
@passenger_required
def hotspot_ordering_page(request, passenger, is_textinput):
    translation.activate(LANG_CODE)

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
                key = submit_test_computation(orders, params=params, computation_set_name=name)
                response = u"Orders submitted for calculation: %s" % key
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

        key = submit_test_computation(orders, params=params, computation_set_id=computation_set.id)
        return JSONResponse({'content': u"Orders submitted for calculation: %s" % key})

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
                         'toleration_factor_minutes': c.toleration_factor_minutes} for c in
                                                                                   computation_set.members.filter(
                                                                                       status=RideComputationStatus.COMPLETED)]

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
                    price = hotspot.get_sharing_price(order.to_lat, order.to_lon, hotspot_datetime.date(),
                                                      hotspot_datetime.time())
                else:
                    order.arrive_time = hotspot_datetime
                    order.depart_time = hotspot_datetime
                    price = hotspot.get_sharing_price(order.from_lat, order.from_lon, hotspot_datetime.date(),
                                                      hotspot_datetime.time())

                passenger = data['passenger']
                order.passenger = passenger
                order.confining_station = passenger.default_sharing_station
                order.language_code = LANG_CODE
                order.save()

                if price and hasattr(passenger, "billing_info"):
                    billing_trx = BillingTransaction(order=order, amount=price, debug=order.debug)
                    billing_trx.save()
                    billing_trx.commit()

                orders.append(order)

    return orders


def submit_test_computation(orders, params, computation_set_name=None, computation_set_id=None):
    key = "test_%s" % str(default_tz_now())
    params.update({'debug': True})
    algo_key = submit_orders_for_ride_calculation(orders, key=key, params=params)

    if algo_key:
        computation = RideComputation(algo_key=algo_key, debug=True)
        computation.change_status(new_status=RideComputationStatus.SUBMITTED)
        computation.toleration_factor = params.get('toleration_factor')
        computation.toleration_factor_minutes = params.get('toleration_factor_minutes')
        order = orders[0]
        computation.hotspot_depart_time = order.depart_time
        computation.hotspot_arrive_time = order.arrive_time

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

    return algo_key