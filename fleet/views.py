import logging
import traceback
import inspect
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from django.utils import simplejson
from django.conf import settings
from djangotoolbox.http import JSONResponse
from fleet import fleet_manager
from ordering.models import SharedRide

def create_ny_isr_ride(request, ride_id):
    if settings.LOCAL:
        isrproxy_id = 2738544
        test_station_id = 1008
    else:
        isrproxy_id = 3673085
        test_station_id = 1713061 # amir_station_1

    test_station_isr_id = 8

    ride = SharedRide.by_id(ride_id)
    if ride and not ride.debug:  # real rides created from stable
        # New York taxi station
        target_station_id = 1529226
        target_station_isr_id = 10
    else:
        target_station_id = test_station_id
        target_station_isr_id = test_station_isr_id


    logging.info(u"create_ny_isr_ride: %s" % u"\n".join([unicode(s) for s in [target_station_id, ride]]))

    if not all([ride, ride.station]):
        response = HttpResponseBadRequest("no ride found or ride not assigned to station")
    elif not ride.station.id == target_station_id:
        response = HttpResponseBadRequest("wrong station: ride.station=%s target_station=%s" % (ride.station, target_station_id))
    else:
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