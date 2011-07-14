# Create your views here.
from django.utils.translation import get_language_from_request
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from ordering.models import Passenger
import settings

def hotspot_ordering_page(request):
    # these should match the fields of utils.Address._fields
    hidden_fields = ["city", "street_address", "house_number", "country", "geohash", "lon", "lat"]

    telmap_user = settings.TELMAP_API_USER
    telmap_password = settings.TELMAP_API_PASSWORD
    telmap_languages = 'he' if str(get_language_from_request(request)) == 'he' else 'en'
    country_code = settings.DEFAULT_COUNTRY_CODE

    passenger = Passenger.from_request(request)


    return render_to_response('hotspot_ordering_page.html', locals(), context_instance=RequestContext(request))


