import logging
import common.urllib_adaptor as urllib2
from django.utils import simplejson
from django.conf import settings
from geocode import telmap_request, get_text_from_element

def calculate_time_and_distance(from_lon, from_lat, to_lon, to_lat):
    """
    Returns estimated time and distance as floats.
    """
    return telmap_calculate_time_and_distance(from_lon, from_lat, to_lon, to_lat)

def telmap_calculate_time_and_distance(from_lon, from_lat, to_lon, to_lat, return_cities=False, return_streets=False):
    """
    Uses the Telmap API (http://api.navigator.telmap.com/xmlwiki/Wiki.jsp?page=General#section-General-RouteRequest)
    to calculate the time &amp; distance between the 2 given locations.
    """
    logging.info("telmap_route")
    route_response = telmap_request({"from_lon": from_lon, "from_lat": from_lat, "to_lon": to_lon, "to_lat": to_lat},
                                   "telmap_route.xml")

    d = float(get_text_from_element(route_response, "totalDistanceInMeters") or 0.0)
    t = float(get_text_from_element(route_response, "totalTimeSeconds") or 0.0)

    result = {
        "estimated_distance":   d,
        "estimated_duration":   t
    }

    return result

def waze_calculate_time_and_distance(from_lon, from_lat, to_lon, to_lat, return_cities=False, return_streets=False):
    """
    Uses the Waze API (http://www.waze.co.il/RoutingManager/routingRequest)
    to calculate the time &amp; distance between the 2 given locations.
    Note that only the 1st alternative path Waze provides is considered.
    """
    url = 'http://www.waze.co.il/RoutingManager/routingRequest?' + \
            'from=x:%s+y:%s+bd:true' % (from_lon, from_lat) + \
            '&to=x:%s+y:%s+bd:true+st_id:46317' % (to_lon, to_lat) + \
            '&returnJSON=true&returnGeometries=true&returnInstructions=false' + \
            '&timeout=60000&nPaths=1&token=%s' % settings.WAZE_API_TOKEN
    json = urllib2.urlopen(url, deadline=10).read()
    result = simplejson.loads(json)

    t, d = 0, 0
    for segment in result["response"]["results"]:
        t = t + segment["crossTime"]
        d = d + segment["length"]
    result = {
        "estimated_distance":   d,
        "estimated_duration":   t
    }

    return result
