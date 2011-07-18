# Create your views here.
from datetime import timedelta
import logging
from django.views.decorators.csrf import csrf_exempt
from google.appengine.api.urlfetch import fetch, POST
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.utils import simplejson
from django.utils.translation import get_language_from_request
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from ordering.models import Passenger, Order
import settings

# SETTINGS
from sharing.models import SharedRide, RidePoint, StopType

SHARING_ENGINE_URL = "http://waybetter-route-service2.appspot.com/routeservicega1"
WEB_APP_URL = "http://sharing.latest.waybetter-app.appspot.com/"

def hotspot_ordering_page(request):
    # these should match the fields of utils.Address._fields
    hidden_fields = ["city", "street_address", "house_number", "country", "geohash", "lon", "lat"]

    telmap_user = settings.TELMAP_API_USER
    telmap_password = settings.TELMAP_API_PASSWORD
    telmap_languages = 'he' if str(get_language_from_request(request)) == 'he' else 'en'
    country_code = settings.DEFAULT_COUNTRY_CODE

    passenger = Passenger.from_request(request)


    return render_to_response('hotspot_ordering_page.html', locals(), context_instance=RequestContext(request))


@csrf_exempt
def ride_calculation_complete(request):
    logging.info("ride_calculation_complete: %s" % request)
    result_id = request.POST.get('id')
    if result_id:
        fetch_ride_results(result_id)

    return HttpResponse("OK")


# UTILITY FUNCTIONS
def submit_orders_for_ride_calculation(orders):
    payload = {
        "orders":       [o.serialize_for_sharing() for o in orders],
        "callback_url": reverse(ride_calculation_complete, prefix=WEB_APP_URL)
    }
    payload = simplejson.dumps(payload)
    logging.info("payload = %s" % payload)

    return fetch(SHARING_ENGINE_URL, payload="submit=%s" % payload, method=POST)

def fetch_ride_results(result_id):
    result = fetch(SHARING_ENGINE_URL, payload="get=%s" % result_id, method=POST)
    data = {}
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


    return data