from api.handlers import OrderRideHandler, RideEstimateHanlder
from django.conf.urls.defaults import *
from piston.resource import Resource

CURRENT_VERSION = 1

order_ride_handler = Resource(OrderRideHandler)
ride_estimate_handler = Resource(RideEstimateHanlder)

urlpatterns = patterns('',
    url(r'order_ride/$', order_ride_handler, { 'emitter_format': 'xml'}, name="order_ride_api"),
    url(r'get_ride_estimate/$', ride_estimate_handler, { 'emitter_format': 'xml'}, name="get_ride_estimation_api" ),
)

