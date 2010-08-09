from django.http import HttpResponseBadRequest, HttpResponse
from common.geocode import geocode, DEFAULT_RESULT_MAX_SIZE
from django.utils import simplejson

ADDRESS_PARAMETER = "address"
MAX_SIZE_PARAMETER = "max_size"

def resolve_address(request):
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

    return HttpResponse(simplejson.dumps(geocoding_results))
