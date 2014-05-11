import base64
import hashlib
import hmac
import re
from common.tz_support import utc_now, unix_time
from django.conf import settings
from google.appengine.api.urlfetch import fetch
import urllib
import logging
import simplejson

from geo.models import GoogleBounds

GOOGLE_CLIENT_ID = '***REMOVED***'
GOOGLE_CRYPTO_KEY = '***REMOVED***'

base_url_re = re.compile(r'https?://[^/]+')

def geocode(address, **kwargs):
    return get_gmaps_results(address=address, **kwargs)

def reverse_geocode(lat, lon, **kwargs):
    latlng = "%s,%s" % (lat, lon)
    return get_gmaps_results(latlng=latlng, **kwargs)

def route(start_lat, start_lng, end_lat, end_lng, sensor=False):
    response = google_directions_request(start_lat, start_lng, end_lat, end_lng, alternatives=True, sensor=sensor)
    result = None
    if response and response.content:
        data = simplejson.loads(response.content)
        if data.get("status") == "OK":
            result = data["routes"]

    return result

def get_shortest_duration(start_lat, start_lng, end_lat, end_lng, sensor=False, use_traffic=True):
    route_results = route(start_lat, start_lng, end_lat, end_lng, sensor=sensor)
    if route_results:
        key = 'duration_in_traffic' if (use_traffic and route_results[0]['legs'][0]['duration_in_traffic']) else 'duration'
        sorted_routes = sorted(route_results, key=lambda route: route['legs'][0][key]['value'])
        return sorted_routes[0]['legs'][0][key]['value']

    return None
def get_gmaps_results(address=None, latlng=None, **kwargs):
    response = gmaps_request(address, latlng, **kwargs)

    results = []
    if response:
        data = simplejson.loads(response.content)

        status = data.get("status")
        logging.info("google geocode status: %s" % status)

        if status == "OK":
            results = data['results']

    return results

def gmaps_request(address=None, latlng=None, bounds=None, region=None, lang_code=None, sensor=False, output="json"):
    # see WS API http://code.google.com/apis/maps/documentation/geocoding/
    params = {
        'bounds': bounds.to_query_string() if isinstance(bounds,GoogleBounds) else bounds,
        'region': region,
        'language': lang_code,
        'sensor': 'true' if sensor else 'false',
        'components': 'country:%s' % settings.DEFAULT_COUNTRY_CODE
    }
    if address:
        params['address'] = unicode(address).encode('utf-8')
    elif latlng:
        params['latlng'] = latlng

    url = "http://maps.googleapis.com/maps/api/geocode/%s" % output
    logging.info("gmaps request: %s" % url)

    response = sign_and_fetch(url, params)

    return response

def google_directions_request(start_lat, start_lng, end_lat, end_lng, output="json", alternatives=False, sensor=False, departure_time=None):
    # see https://developers.google.com/maps/documentation/directions/
    params = {
        'origin': '%s,%s' % (start_lat, start_lng),
        'destination' : '%s,%s' % (end_lat, end_lng),
        'sensor': simplejson.dumps(sensor) ,
        'alternatives': simplejson.dumps(alternatives),
        'departure_time': unix_time(departure_time) if departure_time else unix_time(utc_now())
    }

    url = "http://maps.googleapis.com/maps/api/directions/%s" % output
    logging.info("google_direction_request: %s" % url)
    response = sign_and_fetch(url, params)

    return response

def sign_and_fetch(url, parameters):
    # see: https://developers.google.com/maps/documentation/business/webservices#digital_signatures
    parameters['client'] = GOOGLE_CLIENT_ID
    logging.info("parameters = '%s'" % parameters)
    encoded_params = urllib.urlencode(parameters)
    url_to_sign = "%s?%s" % (base_url_re.split(url)[1], encoded_params)

    key = base64.urlsafe_b64decode(GOOGLE_CRYPTO_KEY)
    signature = hmac.new(key, url_to_sign, hashlib.sha1)
    encoded_signature = base64.urlsafe_b64encode(signature.digest())

    final_url = "%s?%s&signature=%s" % (url, encoded_params, encoded_signature)
    logging.info("final_url = '%s'" % final_url)
    return fetch(final_url)
