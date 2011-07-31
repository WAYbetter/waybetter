from django.template.loader import get_template
from django.contrib.auth import logout
from google.appengine.api import channel
from google.appengine.api.taskqueue import taskqueue
from google.appengine.api.urlfetch import fetch, POST
from django.views.decorators.csrf import csrf_exempt
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect, HttpResponseForbidden
from django.utils import simplejson
from django.utils.translation import get_language_from_request
from django.shortcuts import render_to_response, get_object_or_404
from django.template.context import RequestContext, Context
from common.decorators import internal_task_on_queue, catch_view_exceptions, receive_signal
from common.forms import DatePickerForm
from common.tz_support import  default_tz_now, set_default_tz_time, utc_now, total_seconds
from djangotoolbox.http import JSONResponse
from ordering.decorators import passenger_required_no_redirect, work_station_required, station_or_workstation_required
from ordering.forms import OrderForm
from ordering.models import Passenger, Order, SharedRide, RidePoint, StopType, Driver, Taxi, ACCEPTED, ASSIGNED, TaxiDriverRelation, COMPLETED, NOT_TAKEN, TIMED_OUT
from ordering.util import send_msg_to_passenger, send_msg_to_driver
from sharing import signals
from sharing.forms import ConstraintsForm
from datetime import timedelta, datetime, time, date
import logging
import settings
import re
import sharing_dispatcher # so that receive_signal decorator will be evaluted

SHARING_ENGINE_URL = "http://waybetter-route-service2.appspot.com/routeservicega1"
WEB_APP_URL = "http://sharing.latest.waybetter-app.appspot.com/"

# these should match the fields of utils.Address._fields
HIDDEN_FIELDS = ["city", "street_address", "house_number", "country", "geohash", "lon", "lat"]
POINT_ID_REGEXPT = re.compile("^(p\d+)_")

@passenger_required_no_redirect
def hotspot_ordering_page(request, passenger):
    if request.method == 'POST':
        response = ''
        hotspot_type_raw = request.POST.get("hotspot_type", None)

        if hotspot_type_raw in ["pickup", "dropoff"]:
            hotspot_type, point_type = ("from", "to") if hotspot_type_raw == "pickup" else ("to", "from")
            data = request.POST.copy()
            data['passenger'] = passenger
            orders = create_orders_from_hotspot(data, hotspot_type, point_type)

            if orders:
                params = {"toleration_factor": float(request.POST.get("time_const_frac") or 0),
                          "toleration_factor_minutes": int(request.POST.get("time_const_min") or 0)}
                res = submit_orders_for_ride_calculation(orders, params)
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
        hotspot_times = sorted( map(lambda i : "%d:00" % i, range(default_tz_now().hour,24)) + map(lambda i : "%d:30" % i, range(default_tz_now().hour,24)), key=lambda v: int(v.split(":")[0])) # sorry about that :)

        telmap_user = settings.TELMAP_API_USER
        telmap_password = settings.TELMAP_API_PASSWORD
        telmap_languages = 'he' if str(get_language_from_request(request)) == 'he' else 'en'
        country_code = settings.DEFAULT_COUNTRY_CODE

        passenger = Passenger.from_request(request)
        constraints_form = ConstraintsForm()

        return render_to_response('hotspot_ordering_page.html', locals(), context_instance=RequestContext(request))


@csrf_exempt
def ride_calculation_complete(request):
    logging.info("ride_calculation_complete: %s" % request)
    result_id = request.POST.get('id')
    if result_id:
        task = taskqueue.Task(url=reverse(fetch_ride_results_task), params={"result_id": result_id})
        q = taskqueue.Queue('orders')
        q.add(task)

    return HttpResponse("OK")


@csrf_exempt
@catch_view_exceptions
@internal_task_on_queue("orders")
def fetch_ride_results_task(request):
    result_id = request.POST["result_id"]
    result = fetch(SHARING_ENGINE_URL, payload="get=%s" % result_id, method=POST, deadline=30)
    content = result.content.strip()
    if result.status_code == 200 and content:
        data = simplejson.loads(content.decode("utf-8"))
        for ride_data in data["m_Rides"]:
            order = Order.by_id(ride_data["m_OrderInfos"].keys()[0])
            ride = SharedRide()
            if order.depart_time:
                ride.depart_time = order.depart_time
                ride.arrive_time = ride.depart_time + timedelta(seconds=ride_data["m_Duration"])
            else:
                ride.arrive_time = order.arrive_time
                ride.depart_time = ride.arrive_time - timedelta(seconds=ride_data["m_Duration"])

#            hack for testing
#            ride.depart_time = datetime.now() + timedelta(minutes=3)
#            ride.arrive_time = ride.depart_time + timedelta(seconds=ride_data["m_Duration"])

            ride.save()
            for point_data in ride_data["m_RidePoints"]:
                point = RidePoint()
                point.type = StopType.PICKUP if point_data["m_Type"] == "ePickup" else StopType.DROPOFF
                point.lon = point_data["m_PointAddress"]["m_Longitude"]
                point.lat = point_data["m_PointAddress"]["m_Latitude"]
                point.address = point_data["m_PointAddress"]["m_Name"]
                point.stop_time = ride.depart_time + timedelta(seconds=point_data["m_offset_time"])
                point.ride = ride
                point.save()

                for order_id in point_data["m_OrderIDs"]:
                    order = Order.by_id(int(order_id))
                    order.ride = ride
                    if point.type == StopType.PICKUP:
                        order.pickup_point = point
                    else:
                        order.dropoff_point = point
                    order.save()

            signals.ride_created_signal.send(sender='fetch_ride_results', obj=ride)

    return HttpResponse("OK")


@work_station_required
def sharing_workstation_home(request, work_station, workstation_id):
    if work_station.id != int(workstation_id):
        logout(request)
        return HttpResponseRedirect(request.path)

    is_popup = True

    shared_rides = SharedRide.objects.filter(station=work_station.station, status__in=[ASSIGNED, ACCEPTED])
#    shared_rides = SharedRide.objects.filter(station=work_station.station, status__in=[ASSIGNED, ACCEPTED], depart_time__gte=datetime.now() )


    rides_data = simplejson.dumps([ride.serialize_for_ws() for ride in shared_rides])
    taxis_data = simplejson.dumps(
        [{'id': taxi.id, 'number': taxi.number} for taxi in Taxi.objects.filter(station=work_station.station)])

    assigned = ASSIGNED
    accepted = ACCEPTED
    timed_out = TIMED_OUT
    token = channel.create_channel(work_station.generate_new_channel_id())

    return render_to_response('sharing_workstation_home.html', locals(), context_instance=RequestContext(request))


@station_or_workstation_required
def station_tools(request, station):
    is_popup = True
    page_specific_class = "station_tools station_history"
    return render_to_response('station_tools.html', locals(), context_instance=RequestContext(request))


@station_or_workstation_required
def station_history(request, station):
    is_popup = True
    page_specific_class = "station_history"

    if request.method == 'POST': # date picker form submitted
        form = DatePickerForm(request.POST)
        if form.is_valid():
            start_date = datetime.combine(form.cleaned_data["start_date"], time.min)
            end_date = datetime.combine(form.cleaned_data["end_date"], time.max)
            rides = SharedRide.objects.filter(station=station, status__in=[ACCEPTED, COMPLETED],
                                              depart_time__gte=start_date, depart_time__lte=end_date).order_by('depart_time')
            return JSONResponse({'rides_data': [ride.serialize_for_ws() for ride in rides]})
        else:
            return JSONResponse({'error': 'error'})
    else:
        form = DatePickerForm()
        end_date = datetime.combine(date.today(), time.max)
        start_date = datetime.combine(end_date - timedelta(weeks=1), time.min)
        rides = SharedRide.objects.filter(station=station, status__in=[ACCEPTED, COMPLETED], depart_time__gte=start_date
                                          , depart_time__lte=end_date).order_by('depart_time')
        rides_data = simplejson.dumps([ride.serialize_for_ws() for ride in rides])

        # stringify the dates to the format used in the page
        start_date, end_date = start_date.strftime("%d/%m/%Y"), end_date.strftime("%d/%m/%Y")
        return render_to_response('station_history.html', locals(), context_instance=RequestContext(request))


@work_station_required
def get_drivers_for_taxi(request, work_station):
    taxi_id = request.GET.get("taxi_id")
    taxi = get_object_or_404(Taxi, id=taxi_id)
    if taxi.station != work_station.station:
        return HttpResponseBadRequest("Cannot query other stations taxis")

    taxi_drivers = TaxiDriverRelation.objects.filter(taxi=taxi)
    drivers_data = [{'id': taxi_driver.driver.id, 'name': taxi_driver.driver.name} for taxi_driver in taxi_drivers]

    return JSONResponse(drivers_data)


@work_station_required
def show_ride(request, work_station, ride_id):
    ride = get_object_or_404(SharedRide, id=ride_id)
    if ride.station != work_station.station:
        return HttpResponseForbidden()

    is_popup = True
    telmap_user = settings.TELMAP_API_USER
    telmap_password = settings.TELMAP_API_PASSWORD
    telmap_languages = 'he' if str(get_language_from_request(request)) == 'he' else 'en'

    points = simplejson.dumps([{'id': p.id, 'lat': p.lat, 'lon': p.lon, 'address': p.address, 'type': p.type}
                                for p in sorted(ride.points.all(), key=lambda p: p.stop_time)])

    pickup = StopType.PICKUP
    dropoff = StopType.DROPOFF

    return render_to_response('ride_on_map.html', locals(), context_instance=RequestContext(request))


@work_station_required
def accept_ride(request, work_station):
    ride_id = request.POST.get("ride_id", None)
    taxi_id = request.POST.get("taxi_id", None)
    driver_id = request.POST.get("driver_id", None)

    response = HttpResponseBadRequest("Invalid arguments")
    if all([ride_id, taxi_id, driver_id]):
        ride = SharedRide.by_id(ride_id)
        if ride.depart_time > utc_now():
            taxi = Taxi.by_id(taxi_id)
            driver = Driver.by_id(driver_id)
            if all([ride, taxi, driver]):
                ride.driver = driver
                ride.taxi = taxi
                ride.change_status(new_status=ACCEPTED) # calls save()
                signals.ride_status_changed_signal.send(sender='accept_ride', obj=ride, status=ACCEPTED)

                response = HttpResponse("OK")
        else:
            response = HttpResponseBadRequest("You cannot accept a past order")

    return response


@work_station_required
def complete_ride(request, work_station):
    ride_id = request.POST.get("ride_id", None)
    try:
        ride = SharedRide.by_id(ride_id)
        ride.change_status(old_status=ACCEPTED, new_status=COMPLETED)
        signals.ride_status_changed_signal.send(sender='accept_ride', obj=ride, status=COMPLETED)
        return HttpResponse("OK")

    except Exception:
        logging.error("error setting ride %s as completed" % ride_id)
        return HttpResponseBadRequest("Error")

# UTILITY FUNCTIONS

@receive_signal(signals.ride_status_changed_signal)
def send_ride_notifications(sender, obj, status, **kwargs):
    if status == ACCEPTED:
        ride = obj

        # notify driver
        task = taskqueue.Task(url=reverse(notify_driver_task), params={"driver_id": ride.driver.id, "msg": get_driver_msg(ride)})
        q = taskqueue.Queue('ride-notifications')
        q.add(task)

        # notify passengers
        pickups = ride.points.filter(type=StopType.PICKUP)
        for p in pickups:
            passengers = [order.passenger for order in p.pickup_orders.all()]
            for passenger in passengers:
                task = taskqueue.Task(url=reverse(notify_passenger_task), params={"passenger_id": passenger.id, "msg": get_passenger_msg(passenger, ride)})
                q = taskqueue.Queue('ride-notifications')
                q.add(task)


@csrf_exempt
@catch_view_exceptions
@internal_task_on_queue("ride-notifications")
def notify_driver_task(request):
    driver = Driver.by_id(request.POST['driver_id'])
    msg = request.POST.get('msg', None)
    send_msg_to_driver(driver, msg)

    return HttpResponse("OK")


@csrf_exempt
@catch_view_exceptions
@internal_task_on_queue("ride-notifications")
def notify_passenger_task(request):
    passenger = Passenger.by_id(request.POST['passenger_id'])
    msg = request.POST.get('msg', None)
    send_msg_to_passenger(passenger, msg)

    return HttpResponse("OK")


def get_driver_msg(ride):
    t = get_template("driver_notification_msg.template")
    template_data = {'pickups':
                         [{'address': p.address,
                           'time': p.stop_time.strftime("%H:%M"),
                           'num_passengers': p.pickup_orders.count(),
                           'phones': [order.passenger.phone for order in p.pickup_orders.all()]}

                         for p in ride.points.filter(type=StopType.PICKUP).order_by("stop_time")],

                     'dropoffs':
                         [{'address': p.address,
                           'time': p.stop_time.strftime("%H:%M"),
                           'num_passengers': p.dropoff_orders.count(),
                           'phones': [order.passenger.phone for order in p.dropoff_orders.all()]}

                         for p in ride.points.filter(type=StopType.DROPOFF).order_by("stop_time")]
                    }
    return t.render(Context(template_data))


def get_passenger_msg(passenger, ride):
    t = get_template("passenger_notification_msg.template")

    orders = [{'pickup_time': o.pickup_point.stop_time.strftime("%H:%M"), 'pickup_address': o.pickup_point.address,
               'dropoff_time': o.dropoff_point.stop_time.strftime("%H:%M"), 'dropoff_address': o.dropoff_point.address}
            for o in Order.objects.filter(passenger=passenger, ride=ride)]

    template_data = {'orders': orders, 'driver': ride.driver}
    return t.render(Context(template_data))


def create_orders_from_hotspot(data, hotspot_type, point_type):
    fields = ["raw"] + HIDDEN_FIELDS

    hotspot_data = {}
    for f in fields:
        hotspot_data["%s_%s" % (hotspot_type, f)] = data.get("hotspot_%s" % f, None)

    orders = []
    if all(hotspot_data.values()):
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
                order.passenger = data['passenger']
                hotspot_datetime = datetime.combine(default_tz_now().date(),
                                                    datetime.strptime(data.get("hotspot_time"), "%H:%M").time())

                hotspot_datetime = set_default_tz_time(hotspot_datetime)
                if hotspot_type == "from":
                    order.depart_time = hotspot_datetime
                else:
                    order.arrive_time = hotspot_datetime

                order.save()
                orders.append(order)

    return orders


def submit_orders_for_ride_calculation(orders, params=None):
    payload = {
        "orders": [o.serialize_for_sharing() for o in orders],
        "callback_url": reverse(ride_calculation_complete, prefix=WEB_APP_URL)
    }

    if params:
        payload["parameters"] = {"car_availability":
                                         {"car_types": [{"cost_multiplier": 1, "max_passengers": 3}],
                                          "m_Availability": [{"Key": {"cost_multiplier": 1, "max_passengers": 3}, "Value": 10000}]},
                                 "toleration_factor": params['toleration_factor'],
                                 "toleration_factor_minutes": params['toleration_factor_minutes']}

    payload = simplejson.dumps(payload)
    logging.info("payload = %s" % payload)

    return fetch(SHARING_ENGINE_URL, payload="submit=%s" % payload, method=POST, deadline=30)