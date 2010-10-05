import common.urllib_adaptor as urllib2
from django.utils import simplejson
from django.conf import settings
from datetime import datetime


def calculate_time_and_distance(from_x, from_y, to_x, to_y):
    return waze_calculate_time_and_distance(from_x, from_y, to_x, to_y)


def waze_calculate_time_and_distance(from_x, from_y, to_x, to_y, return_cities=False, return_streets=False):
    """
    Uses the Waze API (http://www.waze.co.il/RoutingManager/routingRequest)
    to calculate the time &amp; distance between the 2 given locations.
    Note that only the 1st alternative path Waze provides is considered.
    """
    url = 'http://www.waze.co.il/RoutingManager/routingRequest?' + \
            'from=x:%s+y:%s+bd:true' % (from_x, from_y) + \
            '&to=x:%s+y:%s+bd:true+st_id:46317' % (to_x, to_y) + \
            '&returnJSON=true&returnGeometries=true&returnInstructions=false' + \
            '&timeout=60000&nPaths=1&token=%s' % settings.WAZE_API_TOKEN
    json = urllib2.urlopen(url).read()
    result = simplejson.loads(json)

    t, d = 0, 0
    for segment in result["response"]["results"]:
        t = t + segment["crossTime"]
        d = d + segment["length"]
    result = {
        "estimated_distance":       d,
        "estimated_duration":   t
    }

    return result
