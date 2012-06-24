import logging
import traceback
import inspect
import datetime
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from django.utils import simplejson
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from common.decorators import force_lang
from common.tz_support import set_default_tz_time
from djangotoolbox.http import JSONResponse
from fleet import fleet_manager
from fleet.fleet_manager import POSITION_CHANGED
from ordering.models import SharedRide, RideEvent, PickMeAppRide

def create_ny_isr_ride(request, ride_id):
    ride = SharedRide.by_id(ride_id)
    if not ride:
        msg = "no SharedRide found with id=%s" % ride_id
        logging.error(msg)
        return HttpResponseBadRequest(msg)

    if settings.LOCAL:
        isrproxy_id = 2738544
        test_station_id = 1008
    else:
        isrproxy_id = 3673085
        test_station_id = 1713061 # amir_station_1

    if ride.debug:
        target_station_id = test_station_id
        target_station_isr_id = 8 # test station isr id
    else:
        # real rides created from stable - send to New York taxi station
        target_station_id = 1529226
        target_station_isr_id = 10

    logging.info(u"create_ny_isr_ride: %s" % u", ".join([unicode(s) for s in [target_station_id, ride]]))

    if not (ride.station and ride.station.id == target_station_id):
        msg = "wrong station: ride.station=%s target_station=%s" % (ride.station, target_station_id)
        logging.error(msg)
        response = HttpResponseBadRequest(msg)
    else:
        # fix the station data since stable.Station does not have fleet field
        if not ride.station.fleet_station_id:
            ride.station.fleet_station_id = target_station_isr_id
            ride.station.save()

        ride.dn_fleet_manager_id = isrproxy_id
        ride.save()

        result = fleet_manager.create_ride(ride)
        response = HttpResponse(str(result))

    return response

def get_ride(request, ride_id):
    from fleet import isr_tests
    result = str(isr_tests.get_ride(ride_id, False))
    if request.is_ajax():
        return JSONResponse({'result': result})
    else:
        return HttpResponse(result)


def isr_testpage(request):
    from fleet import isr_tests

    if request.method == "POST":
        result = ""
        method_name = request.POST.get("method_name")
        try:
            method = getattr(isr_tests, method_name)
            args = inspect.getargspec(method)[0]
            values = [request.POST.get(arg) for arg in args]
            result = method(*values)

        except Exception, e:
            trace = traceback.format_exc()
            result = trace

        try:
            result = simplejson.dumps(result)
        except TypeError: # not json serializable
            result = str(result)

        return JSONResponse({'result': result})
    else:
        methods = []
        method_type = type(lambda x: x)
        for attr_name in dir(isr_tests):
            if attr_name.startswith("_"):
                continue
            attr = getattr(isr_tests, attr_name)
            if type(attr) == method_type:
                args = inspect.getargspec(attr)[0]
                methods.append({'name': attr.func_name, 'args': args, 'doc': attr.func_doc or ""})

        return render_to_response("isr_testpage.html", locals(), RequestContext(request))

@staff_member_required
@force_lang("en")
def isr_status_page(request):
    position_changed = POSITION_CHANGED
    return render_to_response("isr_status_page.html", locals(), RequestContext(request))

@staff_member_required
def get_ride_events(request):
    import dateutil.parser


    from_date = dateutil.parser.parse(request.GET.get("from_date"))
    to_date = dateutil.parser.parse(request.GET.get("to_date"))

    from_date = datetime.datetime.combine(from_date, set_default_tz_time(datetime.time.min))
    to_date = datetime.datetime.combine(to_date, set_default_tz_time(datetime.time.max))

    logging.info("get_ride_events: %s, %s" % (from_date, to_date))
    shared_rides = {}
    pickmeapp_rides = {}
    events = RideEvent.objects.filter(create_date__gt=from_date, create_date__lt=to_date)
    for e in events:
        taxi = e.taxi_id
        if e.shared_ride_id:
            if e.shared_ride_id in shared_rides:
                shared_rides[e.shared_ride_id]["events"].append(e.serialize_for_status_page())
                if taxi and not shared_rides[e.shared_ride_id]['taxi']:
                    shared_rides[e.shared_ride_id]['taxi'] = taxi
            else:
                ride = SharedRide.by_id(e.shared_ride_id)
                shared_rides[e.shared_ride_id] = {
                    "id"        : ride.id,
                    "type"      : "sharing",
                    "taxi"      : taxi,
                    "stops"     : [p.serialize_for_status_page() for p in sorted(ride.points.all(), key=lambda p: p.stop_time)],
                    "events"    : [e.serialize_for_status_page()]
                }
        elif e.pickmeapp_ride_id:
            if e.pickmeapp_ride_id in pickmeapp_rides:
                pickmeapp_rides[e.pickmeapp_ride_id]["events"].append(e.serialize_for_status_page())
                if taxi and not pickmeapp_rides[e.pickmeapp_ride_id]['taxi']:
                    pickmeapp_rides[e.pickmeapp_ride_id]['taxi'] = taxi
            else:
                ride = PickMeAppRide.by_id(e.pickmeapp_ride_id)
                order = ride.order
                stops = [{"lon": order.from_lon,
                         "lat": order.from_lat,
                         "address": order.from_raw,
                         "time": order.create_date.strftime("%d/%m/%y %H:%M")}]

                if order.to_lon and order.to_lat:
                    stops.append({
                        "lon": order.to_lon,
                        "lat": order.to_lat,
                        "address": order.to_raw,
                        "time": order.create_date.strftime("%d/%m/%y %H:%M")})

                pickmeapp_rides[e.pickmeapp_ride_id] = {
                    "id"        : ride.id,
                    "type"      : "pickmeapp",
                    "taxi"      : taxi,
                    "stops"     : stops,
                    "events"    : [e.serialize_for_status_page()]

                }
    result = shared_rides.values() + pickmeapp_rides.values()

    return JSONResponse(result)