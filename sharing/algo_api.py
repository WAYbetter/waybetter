from google.appengine.api.urlfetch import  POST
from django.utils import simplejson
from common.util import safe_fetch, Enum, first
from ordering.models import SHARING_TIME_MINUTES, SHARING_DISTANCE_METERS, StopType
from datetime import  datetime
import urllib
import logging
from pricing.models import TARIFFS

NEW_ORDER_ID = 0

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
    PRICE = "m_Price"
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
    TOTAL_DISTANCE = "m_TotalDistance"
    TYPE = "m_Type"

class RideData(object):
    """
    A helper class to access ride data returned by the algorithm
    """
    def __init__(self, raw_ride_data):
        self.raw_ride_data = raw_ride_data

    @property
    def ride_id(self):
        return self.raw_ride_data[AlgoField.RIDE_ID]

    @property
    def duration(self):
        return self.raw_ride_data[AlgoField.REAL_DURATION]

    @property
    def distance(self):
        return self.raw_ride_data[AlgoField.TOTAL_DISTANCE]

    @property
    def cost_data(self):
        return CostData(self.raw_ride_data)

    @property
    def points(self):
        return [PointData(raw_point_data) for raw_point_data in self.raw_ride_data[AlgoField.RIDE_POINTS]]

    def order_price_data(self, order_id, sharing=True):
        order_info = self.raw_ride_data[AlgoField.ORDER_INFOS][str(order_id)]
        if sharing:
            return {
                TARIFFS.TARIFF1: order_info[AlgoField.PRICE_SHARING_TARIFF1],
                TARIFFS.TARIFF2: order_info[AlgoField.PRICE_SHARING_TARIFF2]
            }
        else:
            return {
                TARIFFS.TARIFF1: order_info[AlgoField.PRICE_ALONE_TARIFF1],
                TARIFFS.TARIFF2: order_info[AlgoField.PRICE_ALONE_TARIFF2]
            }

    def order_price(self, order_id, tariff, sharing=True):
        if not tariff:
            return None

        price_data = self.order_price_data(order_id, sharing=sharing)
        return price_data.get(tariff.tariff_type)

    def order_time(self, order_id, sharing=True):
        if sharing:
            return self.raw_ride_data[AlgoField.ORDER_INFOS][str(order_id)][AlgoField.TIME_SHARING]
        else:
            return self.raw_ride_data[AlgoField.ORDER_INFOS][str(order_id)][AlgoField.TIME_ALONE]

    def order_pickup_point(self, order_id):
        """
        @param order_id: order id to look up
        @return: a PointData object for the point data of the given order id. If order id is not found returns None
        """
        raw_pickup_data = first(lambda p: order_id in p[AlgoField.ORDER_IDS] and p[AlgoField.TYPE] == AlgoField.PICKUP, self.raw_ride_data[AlgoField.RIDE_POINTS])
        return PointData(raw_pickup_data) if raw_pickup_data else None

class PointData(object):
    """
    A helper class for point data returned by the algorithm
    """
    def __init__(self, raw_point_data):
        self.raw_point_data = raw_point_data

    @property
    def offset(self):
        return self.raw_point_data[AlgoField.OFFSET_TIME]

    @property
    def lon(self):
        return self.raw_point_data[AlgoField.POINT_ADDRESS][AlgoField.LNG]

    @property
    def lat(self):
        return self.raw_point_data[AlgoField.POINT_ADDRESS][AlgoField.LAT]

    @property
    def address(self):
        return self.raw_point_data[AlgoField.POINT_ADDRESS][AlgoField.ADDRESS]

    @property
    def city_name(self):
        return self.raw_point_data[AlgoField.POINT_ADDRESS][AlgoField.CITY]

    @property
    def stop_type(self):
        return StopType.PICKUP if self.raw_point_data[AlgoField.TYPE] == AlgoField.PICKUP else StopType.DROPOFF

    @property
    def order_ids(self):
        return self.raw_point_data[AlgoField.ORDER_IDS]


class CostData(object):
    def __init__(self, raw_ride_data):
        self.cost_data = {
            TARIFFS.TARIFF1: raw_ride_data[AlgoField.COST_LIST_TARIFF1],
            TARIFFS.TARIFF2: raw_ride_data[AlgoField.COST_LIST_TARIFF2]
        }

    def __str__(self):
        return self.cost_data.__str__()

    def __unicode__(self):
        return self.cost_data.__unicode__()

    def for_tariff_type(self, tariff_type):
        """
        @param tariff_type: a value of pricing.models.TARIFFS
        return a list of {AlgoField.MODEL_ID: '', AlgoField.PRICE: ''} objects
        """
        return self.cost_data.get(tariff_type, [])

    def for_tariff(self, tariff):
        """
        @param tariff: RuleSet instance or None
        return a list of {AlgoField.MODEL_ID: '', AlgoField.PRICE: ''} objects
        """
        if not tariff:
            return []

        return self.for_tariff_type(tariff.tariff_type)

    def for_model_by_tariff(self, model_name, tariff):
        """
        returns None or the cost for the given pricing model and tariff
        """
        cost_models = self.for_tariff(tariff)
        for cost_model in cost_models:
            if cost_model[AlgoField.MODEL_ID] == model_name:
                return cost_model[AlgoField.PRICE]

        return None

    def model_names_for_tariff(self, tariff):
        """
        returns a list of pricing models names (strings) for given tariff
        """
        return [entry[AlgoField.MODEL_ID] for entry in self.for_tariff(tariff)]


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
