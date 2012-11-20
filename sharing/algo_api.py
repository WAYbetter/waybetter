from google.appengine.api.urlfetch import  POST
from django.utils import simplejson
from common.util import safe_fetch, Enum
from ordering.models import SHARING_TIME_MINUTES, SHARING_DISTANCE_METERS
from datetime import  datetime
import urllib
import logging

DEBUG = 1
WAZE = 3
GOOGLE = 4

M2M_ENGINE_DOMAIN = "http://waybetter-route-service3.appspot.com/m2malgo"
SHARING_ENGINE_DOMAIN = "http://waybetter-route-service%s.appspot.com" % GOOGLE
ROUTING_URL = "/".join([SHARING_ENGINE_DOMAIN, "routes"])

class AlgoField(Enum):
    ADDRESS = "m_Address"
    AREA = "m_Area"
    CITY = "m_City"
    COST_LIST_TARIFF1 = "m_AllCosts"
    COST_LIST_TARIFF2 = "m_AllCosts2"
    DEBUG = "m_Debug"
    DISTANCE = "m_Distance"
    DROPOFF = "eDropoff"
    DURATION = "m_Duration"
    LAT = "m_Latitude"
    LNG = "m_Longitude"
    MODEL_ID = "m_ModelID"
    NAME = "m_Name"
    OFFSET_TIME = "m_offset_time"
    ORDER_IDS = "m_OrderIDs"
    ORDER_INFOS = "m_OrderInfos"
    OUTPUT_STAT = "m_OutputStat"
    PICKUP = "ePickup"
    POINT_ADDRESS = "m_PointAddress"
    PRICE_ALONE_TARIFF1 = "m_PriceAlone"
    PRICE_ALONE_TARIFF2 = "m_Price2Alone"
    PRICE_SHARING_TARIFF1 = "m_PriceSharing"
    PRICE_SHARING_TARIFF2 = "m_Price2Sharing"
    REAL_DURATION = "m_RealDuration"
    RIDES = "m_Rides"
    RIDE_ID = "m_RideID"
    RIDE_POINTS = "m_RidePoints"
    TIME_ALONE = "m_TimeAlone"
    TIME_SECONDS = "m_TimeSeconds"
    TIME_SHARING = "m_TimeSharing"
    TYPE = "m_Type"

def find_matches(candidate_rides, order_settings):
    payload = {
        AlgoField.RIDES : [r.serialize_for_algo() for r in candidate_rides],
        "order"         : order_settings.serialize(),
        "parameters"    : {
            "debug"                     : order_settings.debug,
            'toleration_factor_minutes' : SHARING_TIME_MINUTES,
            'toleration_factor_meters'  : SHARING_DISTANCE_METERS
        }
    }

    payload = simplejson.dumps(payload)
    logging.info(u"submit=%s" % unicode(payload, "unicode-escape"))
    dt1 = datetime.now()
    response = safe_fetch(M2M_ENGINE_DOMAIN, payload="submit=%s" % payload, method=POST, deadline=50)
    dt2 = datetime.now()
    logging.info("response=%s" % response.content)

    matches = []
    if response and response.content:
        matches = simplejson.loads(response.content)[AlgoField.RIDES]

    logging.info("%s candidates [%s], %s matches, %s seconds" % (len(candidate_rides),
                                                                ",".join([str(ride.id) for ride in candidate_rides]),
                                                                len(matches),
                                                                (dt2 - dt1).seconds))

    return matches

def calculate_route(start_lat, start_lon, end_lat, end_lon):
    payload = urllib.urlencode({
        "start_latitude": start_lat,
        "start_longitude": start_lon,
        "end_latitude": end_lat,
        "end_longitude": end_lon
    })

    url = "%s?%s" % (ROUTING_URL, payload)
    logging.info("algo route: %s" % url)

    response = safe_fetch(url, deadline=15, notify=False)
    content = response.content.strip() if response else None

    result = {
        "estimated_distance": 0.0,
        "estimated_duration": 0.0
    }

    if content:
        route = simplejson.loads(content)
        if "Error" in route:
            logging.error(route["Error"])
        else:
            result = {
                "estimated_distance": float(route[AlgoField.DISTANCE]),
                "estimated_duration": float(route[AlgoField.TIME_SECONDS])
            }

    return result
