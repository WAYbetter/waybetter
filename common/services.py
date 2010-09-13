import time

from django.http import HttpResponseBadRequest, HttpResponse
from common.geocode import geocode, DEFAULT_RESULT_MAX_SIZE
from django.utils import simplejson
from django.contrib.auth.models import User
from ordering.models import Passenger

ADDRESS_PARAMETER = "term"
MAX_SIZE_PARAMETER = "max_size"



def resolve_address(request, include_order_history=True):
    # get parameters
    if not ADDRESS_PARAMETER in request.GET:
        return HttpResponseBadRequest("Missing address")

    address = request.GET[ADDRESS_PARAMETER]
    size = request.GET.get(MAX_SIZE_PARAMETER) or DEFAULT_RESULT_MAX_SIZE
    try:
        size = int(size)
    except:
        return HttpResponseBadRequest("Invalid value for max_size")


    geocoding_results = geocode(address, max_size=size, add_geohash=True, resolve_to_ids=True)
    history_results = []
    if include_order_history:
        passenger = Passenger.get_passenger_from_request(request)
        if passenger:
            history_results.extend([get_results_from_order(o, "from") for o in passenger.orders.filter(from_raw__icontains=address)])
            history_results.extend([get_results_from_order(o, "to") for o in passenger.orders.filter(to_raw__icontains=address)])


    return HttpResponse(simplejson.dumps({
                                         "geocode": geocoding_results[:size],
                                         "history": history_results[:size]
                                         }))

def get_results_from_order(order, field_prefix):
    return {
        "lat": getattr(order, field_prefix + "_lat"),
        "lon": getattr(order, field_prefix + "_lon"),
        "name": getattr(order, field_prefix + "_raw"),
#        "street": getattr(order, field_prefix + "_street_address"),
        "city": getattr(order, field_prefix + "_city").id,
        "country": getattr(order, field_prefix + "_country").id,
        "geohash": getattr(order, field_prefix + "_geohash"),
    }


def is_username_available(request):
    #TODO_WB:throttle this
    result = False
    username = request.GET.get("username")
    if (username):
        time.sleep(1)
        result = User.objects.filter(username=username).count() == 0

    if result:
        return HttpResponse("true")
    else:
        return HttpResponse("false")