# This Python file uses the following encoding: utf-8

import sys
import logging
from xml.dom import minidom
from common.util import safe_fetch
from django.http import HttpResponse

from google.appengine.api.urlfetch import fetch
from google.appengine.api import memcache

from django.template import Context
from django.template.loader import get_template
from django.utils import simplejson
from django.utils.http import urlquote_plus
from django.conf import settings

from util import get_text_from_element, is_in_hebrew
import geohash
import re
CLEAN_RE = re.compile("ns2:")


DEFAULT_RESULT_MAX_SIZE = 7
TELMAP_LOGIN_CREDENTIALS = 'TELMAP_LOGIN_CREDENTIALS'
TELMAP_XML_API_URL = "http://api.telmap.com/telmapnav/xmlapi/v7"


def geohash_encode(lon, lat):
    return geohash.encode(lat, lon)

def geohash_decode(hash):
    return geohash.decode(hash)

def structured_geocode(country_code, city_name, street_name, house_number, max_size=DEFAULT_RESULT_MAX_SIZE):
    return telmap_structured_geocode(country_code, city_name, street_name, house_number, max_size)

def geocode(str, max_size=DEFAULT_RESULT_MAX_SIZE, add_geohash=True, resolve_to_ids=False, constrain_to_city=None):
    """
    default geocoder
    """
    from common.models import City, Country

    results = telmap_geocode(str, max_size, constrain_to_city)
    logging.info(u"geocoding results for %s: %s\n" % (str,results))

    if add_geohash or resolve_to_ids:
        for result in results:
            if add_geohash:
                result["geohash"] = geohash_encode(result["lon"], result["lat"])

            if resolve_to_ids:
                result["country"] = Country.get_id_by_code(result["country"])

                if is_in_hebrew(result["city"]):
                    result["city"] = City.get_id_by_name_and_country(result["city"], result["country"], add_if_not_found=True)
                else:
                    # try to reverse geocode to get city name in Hebrew
                    reverse_geocode_result = reverse_geocode(result["lat"], result["lon"])
                    if reverse_geocode_result:
                        result["city"] = reverse_geocode_result["city"]
                    else:
                        logging.error("failed to get Hebrew city name from reverse geocode")
                        result["city"] = City.get_id_by_name_and_country(result["city"], result["country"], add_if_not_found=True)

    return results

def osrm_proxy(request, service_name):
    """
    OSRM server is CSRF protected and so we can't make direct requests from our pages.
    """
    osrm_engine = "http://router.project-osrm.org"
    q_url = "%s/%s?%s" % (osrm_engine, service_name, request.META['QUERY_STRING'])

    response = fetch(q_url)
    return HttpResponse(response.content)


def telmap_logout(session_id):
    logging.info("Telmap logout")
    c = Context({
        "session_id": session_id
    })
    t = get_template("telmap_logout.xml")
    res = fetch(TELMAP_XML_API_URL, method="POST", payload=str("requestXML="+urlquote_plus(t.render(c))))
    logging.info(res.content)


def telmap_login():
    """
    Perform a login request to Telmap's servers
    Returns (server_id, session_id) tuple that can be used in subsequent calls and stores it in memcache
    """

    logging.info("Telmap login")
    c = Context({
        "app_name":             "waybetter",
        "username":             settings.TELMAP_API_USER,
        "password":             settings.TELMAP_API_PASSWORD,
        "language_code":        "he",
        "sec_language_code":    "en"
    })

    t = get_template("telmap_login.xml")
#    logging.info(unicode("requestXML="+(t.render(c))))

    res = fetch(TELMAP_XML_API_URL, method="POST", payload=str("requestXML="+urlquote_plus(t.render(c))))
    cleaned_response = clean_telmap_response(res.content)
    login_response = minidom.parseString(cleaned_response)

    server_id = get_text_from_element(login_response, "serverId")
    session_id = get_text_from_element(login_response, "sessionId")

    if server_id and session_id:
        telmap_login_credentials = (server_id, session_id)
        memcache.set(TELMAP_LOGIN_CREDENTIALS, telmap_login_credentials)
        return telmap_login_credentials
    else:
        logging.error('Could not login to Telmap servers')
#        logging.info(res.content)
#        telmap_logout(session_id)
        return None

def google_geocode(str):
    service_url = "http://maps.google.com/maps/geo?"
    key = "***REMOVED***"
    d = {}
    wkt = 'POINT(0.0 0.0)'
    if str is not None and len(str) > 0:
        try:
            service_url = service_url + "q=%s" % str.replace(" ", "+")
            service_url = service_url + "&key=%s" % key
            service_url = service_url + "&output=json"
            service_url = service_url + "&sensor=false"
            result = "{}"
            response = urllib2.urlopen(service_url)
            result = response.read()
            json = simplejson.loads(result)
            #print service_url
            #print json
            d['country'] = json['Placemark'][0]['AddressDetails']['Country']['CountryName'].encode("utf-8")
            coords = json['Placemark'][0]['Point']['coordinates']
            wkt = 'POINT(%s %s)' % (coords[0], coords[1])
        except:
            #print sys.exc_info()
            pass
    return d

def waze_geocode(str, max_size):
    """
    geocode given location

    returns a dictionary
    """
    service_url = "***REMOVED***"
    key = ""
    results = []
    if str and len(str) > 0:
        try:
            service_url = service_url + "q=%s" % str.replace(" ", "+").encode("utf-8")
            service_url = service_url + "&max_results=%d" % max_size
            service_url = service_url + "&token=%s" % key
            response = fetch(service_url)
            json = simplejson.loads(response.content.decode("utf-8"))
            for address in json:
                result = {}

                if not address["location"]:
                    continue
                result["lat"] = address["location"]["lat"]
                result["lon"] = address["location"]["lon"]
                address_parts = address["mobileResult"].split(",")
                result["name"] = address["name"]
                result["country"] = "IL" #TODO_WB: fix this
                result["city"] = address_parts[-3]
                result["street"] = address_parts[-2]

                results.append(result)

        except:
            raise
#            error_info = str(sys.exc_info())
#            logging.error(error_info)

    return results

def waze_reverse_geocode(lon, lat):
    service_url = "***REMOVED***"
    key = ""
    json = []
    if long and lat:
        try:
            service_url = service_url + "x=%s" % lon
            service_url = service_url + "&y=%s" % lat
            service_url = service_url + "&returnJSON=true"
            service_url = service_url + "&token=%s" % key
            response = urllib2.urlopen(service_url)
            result = response.read()
            json = simplejson.loads(result)
        except:
            print sys.exc_info()

    return json

def reverse_geocode(latitude, longitude):
    from common.models import Country, City

    result =  telmap_reverse_geocode(latitude, longitude)
    if result:
        house_number = result.get("house_number")
        if not house_number or not house_number.isdigit():
            return None

        result["country_name"] = result["country"]
        result["country"] = Country.get_id_by_code(result["country"])
        result["city_name"] = result["city"]
        result["city"] = City.get_id_by_name_and_country(result["city"], result["country"], add_if_not_found=True)
        result["geohash"] = geohash_encode(longitude, latitude)

    return result


def get_city_from_location(lon, lat):
    result = reverse_geocode(lat, lon)
    if result:
        city = result.get('city_name', None)
    else:
        city = None

    return city

def telmap_reverse_geocode(latitude, longitude):
    """
    Perform a reverse geocode query via Telmap
    """
    response = telmap_request({
        "longitude":    longitude,
        "latitude":     latitude
    }, 'telmap_reverse_search.xml')
    locations = response.getElementsByTagName("location")
    if locations and locations[0].childNodes:
        return get_address_from_telmap_location(locations[0])
    else:
        return None


def telmap_fetch_results(data, request_template):
    """
    Performs a query to telmap server
    Creates a query XML and sends it to Telmap servers
    Returns parsed result object
    """
    c = Context(data)
    t = get_template(request_template)
    payload = u"sid=%s&requestXML=%s" % (data['server_id'], urlquote_plus(t.render(c)))
#    logging.info(u"sid=%s&requestXML=%s" % (data['server_id'], t.render(c)))
    res = safe_fetch(u"%s?%s" % (TELMAP_XML_API_URL, payload), method="GET", notify=False)#, payload=payload)
    if res:
        cleaned_response = clean_telmap_response(res.content)
        return minidom.parseString(cleaned_response)
    else:
        return None
#    logging.info(res.content)
def telmap_request(data, request_template):
    """
    Wrapper for Telmap requests.
    Handles session login
    """
    if memcache.get(TELMAP_LOGIN_CREDENTIALS): # lazy login
        server_id, session_id = memcache.get(TELMAP_LOGIN_CREDENTIALS)
    else:
        server_id, session_id  = telmap_login()

    data["server_id"] = server_id
    data["session_id"] = session_id
    response = telmap_fetch_results(data, request_template)
    if get_text_from_element(response, 'errorCode') == '1150':
        logging.info("Invalid session, login again")
        server_id, session_id  = telmap_login()
        data["server_id"] = server_id
        data["session_id"] = session_id
        response = telmap_fetch_results(data, request_template)

    return response


def get_addresses_from_telmap_search(search_response):
    results = []
    for location in search_response.getElementsByTagName("location"):
        result = get_address_from_telmap_location(location)
        if result["street_address"] and result["house_number"] and result["city"] and result["lon"] and result["lat"]:
            results.append(result)
    return results


def telmap_structured_geocode(country_code, city_name, street_name, house_number, max_size):
    search_response = telmap_request({
        "query":        street_name,
        "country_code": country_code,
        "max_results":  max_size,
        "city":         city_name,
        "house_number": house_number
    }, "telmap_search.xml")

    return get_addresses_from_telmap_search(search_response)

def telmap_single_line_geocode(query, max_size):
    search_response = telmap_request({
        "query":        query,
        "country_code": 'IL',
        "max_results":  max_size
    }, "telmap_single_line_search.xml")

    return get_addresses_from_telmap_search(search_response)

def telmap_geocode(str, max_size, constrain_to_city):
    logging.info("telmap_geocode")
    if constrain_to_city:
        # extract house number from query string
        import re
        m = re.search(r'(\d+)', str)
        house_number = m.groups()[0] if m else ''
        str = str.replace(house_number, '')

        return telmap_structured_geocode('IL', constrain_to_city.name, str, house_number, max_size)
    else:
        return telmap_single_line_geocode(str, max_size)

def get_address_from_telmap_location(location):
    result = {}
    lat = get_text_from_element(location, "geoPoint", "latitude")
    result["lat"] = float(lat) if lat else lat
    lon = get_text_from_element(location, "geoPoint", "longitude")
    result["lon"] = float(lon) if lon else lon
    result["description"] = get_text_from_element(location, "description", "text")
    result["country"] = get_text_from_element(location, "countryCode", "code")
    result["city"] = get_text_from_element(location, "city", "text")
    result["street_address"] = get_text_from_element(location, "street", "text")
    result["house_number"] = get_text_from_element(location, "houseNumber")
    if result["house_number"]:
        result["name"] = "%s %s, %s" % (result["street_address"], result["house_number"], result["city"])
    else:
        result["name"] = result["description"]

    result["raw"] = result["name"]

    return result

def clean_telmap_response(response):
    return CLEAN_RE.sub("", response)

def flush_memcache(request):
    memcache.delete(TELMAP_LOGIN_CREDENTIALS)
    return HttpResponse("OK")