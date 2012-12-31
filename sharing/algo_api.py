# -*- coding: utf-8 -*-

from google.appengine.api.urlfetch import  POST
from common.models import CityArea
from django.utils import simplejson
from django.conf import settings
from common.util import safe_fetch, Enum, first, clean_values
from ordering.models import SHARING_TIME_MINUTES, SHARING_DISTANCE_METERS, StopType, Order
from datetime import  datetime
import urllib
import logging
from pricing.models import TARIFFS

NEW_ORDER_ID = 0

ALGO_ENGINE_DOMAIN = "http://waybetter-route-service%s.appspot.com" % (4 if settings.DEV else 3)

M2M_ENGINE_URL = "%s/m2malgo" % ALGO_ENGINE_DOMAIN
ROUTING_URL = "%s/routes" % ALGO_ENGINE_DOMAIN

class ALGO_CITY(Enum):
    TEL_AVIV = u'תל אביב יפו'
    BNEI_BRAK = u'בני ברק'
    GIVATAYIM = u'גבעתיים',
    RAMAT_GAN = u'רמת גן',
    RAMAT_HASHARON = u'רמת השרון',
    HERZLIYYA = u'הרצליה',
    RAANANA = u'רעננה'


ALGO_CITY_ALIASES = {
    'tel aviv': ALGO_CITY.TEL_AVIV,
    'bnei brak': ALGO_CITY.BNEI_BRAK,
    'givatayim': ALGO_CITY.GIVATAYIM,
    'ramat gan': ALGO_CITY.RAMAT_GAN,
    'ramat hasharon': ALGO_CITY.RAMAT_HASHARON,
    'herzliyya': ALGO_CITY.HERZLIYYA,
    'raanana': ALGO_CITY.RAANANA
}

def to_algo_city_name(raw_city_name):
    if ALGO_CITY.contains(raw_city_name):
        return raw_city_name

    else:
        clean_raw = raw_city_name.lower().replace("'", "").strip()
        logging.info("clean raw " + clean_raw)
        return ALGO_CITY_ALIASES.get(clean_raw, raw_city_name)


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

    # pricing
    PRICING_TYPE = "m_PricingType"
    INTERCITY_RANGES = "eInterCityRanges"
    INTERCITY_KM = "eInterCityKM"
    INTRACITY_AREAS = "eIntraCitiesAreas"
    ADDITIONAL_METERS = "m_AdditionalMeters"
    ORIGIN_AREA = "m_OriginCityArea"
    DESTINATION_AREA = "m_DestinationCityArea"
    RANGE_NAME = "m_RangeName"


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

    def order_price_data(self, order_id):
        order_data = self.raw_ride_data[AlgoField.ORDER_INFOS][str(order_id)]
        return PriceData(order_data)

    def order_price(self, order_id, tariff, sharing=True):
        if not tariff:
            return None

        price_data = self.order_price_data(order_id)
        return price_data.for_tariff_type(tariff.tariff_type, sharing=sharing)

    def order_time(self, order_id, sharing=True):
        if sharing:
            return self.raw_ride_data[AlgoField.ORDER_INFOS][str(order_id)][AlgoField.TIME_SHARING]
        else:
            return self.raw_ride_data[AlgoField.ORDER_INFOS][str(order_id)][AlgoField.TIME_ALONE]

    def order_pickup_point(self, order_id):
        return self.get_order_point(AlgoField.PICKUP, order_id)

    def order_dropoff_point(self, order_id):
        return self.get_order_point(AlgoField.DROPOFF, order_id)

    def get_order_point(self, point_type, order_id):
        """
        @param point_type: AlgoField.PICKUP or AlgoField.DROPOFF
        @param order_id: order id to look up
        @return: a PointData object for the point data of the given order id. If order id is not found returns None
        """
        raw_point_data = first(lambda p: order_id in p[AlgoField.ORDER_IDS] and p[AlgoField.TYPE] == point_type, self.raw_ride_data[AlgoField.RIDE_POINTS])
        return PointData(raw_point_data) if raw_point_data else None


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

class PriceData(object):
    def __init__(self, raw_order_data):
        self.sharing_price_data = {
            TARIFFS.TARIFF1: raw_order_data[AlgoField.PRICE_SHARING_TARIFF1],
            TARIFFS.TARIFF2: raw_order_data[AlgoField.PRICE_SHARING_TARIFF2]
        }

        self.alone_price_data = {
            TARIFFS.TARIFF1: raw_order_data[AlgoField.PRICE_ALONE_TARIFF1],
            TARIFFS.TARIFF2: raw_order_data[AlgoField.PRICE_ALONE_TARIFF2]
        }

    def __str__(self):
        return "sharing: %s, alone: %s" % (self.sharing_price_data.__str__(), self.alone_price_data.__str__())

    def __unicode__(self):
        return unicode(self.__str__())

    def for_tariff_type(self, tariff_type, sharing=True):
        if sharing:
            return self.sharing_price_data.get(tariff_type)
        else:
            return self.alone_price_data.get(tariff_type)


class CostData(object):
    def __init__(self, raw_ride_data):
        self.cost_data = {
            TARIFFS.TARIFF1: raw_ride_data[AlgoField.COST_LIST_TARIFF1],
            TARIFFS.TARIFF2: raw_ride_data[AlgoField.COST_LIST_TARIFF2]
        }

    def __str__(self):
        return self.cost_data.__str__()

    def __unicode__(self):
        return unicode(self.cost_data)

    def for_tariff_type(self, tariff_type):
        """
        @param tariff_type: a value of pricing.models.TARIFFS
        return a list of {AlgoField.MODEL_ID: '', AlgoField.PRICE: ''} objects
        """
        return self.cost_data.get(tariff_type, [])

    def for_tariff(self, tariff):
        """
        @param tariff: RuleSet instance or None
        return a list of CostDetail objects
        """
        if not tariff:
            return []

        return self.for_tariff_type(tariff.tariff_type)

    def model_names_for_tariff(self, tariff):
        """
        returns a list of pricing models names (strings) for given tariff
        """
        return [entry[AlgoField.MODEL_ID] for entry in self.for_tariff(tariff)]

    def get_details(self, tariff, model_name):
        """
        returns CostDetails instance or None
        """
        list_of_cost_details = self.for_tariff(tariff)
        for entry in list_of_cost_details:
            if entry[AlgoField.MODEL_ID] == model_name:
                return CostDetails(entry)

        return None


class CostDetails:
    def __init__(self, details=None):
        self._details = details or {}

    @staticmethod
    def serialize(obj):
        if not isinstance(obj, CostDetails):
            return None

        srz = {
            'model': obj.model,
            'cost': obj.cost,
            'type': obj.type,
            'range': obj.range,
            'by_areas': obj.by_areas,
            'origin_area': "%s, %s" % (obj.origin_area.get("City"), obj.origin_area.get("Area")) if obj.by_areas else '',
            'destination_area': "%s, %s" % (obj.destination_area.get("City"), obj.destination_area.get("Area")) if obj.by_areas else '',
            'additional_meters': obj.additional_meters
        }

        return srz

    @property
    def model(self):
        return self._details.get(AlgoField.MODEL_ID)
    @property
    def cost(self):
        return self._details.get(AlgoField.PRICE)
    @property
    def range(self):
        return self._details.get(AlgoField.RANGE_NAME)
    @property
    def origin_area(self):
        return self._details.get(AlgoField.ORIGIN_AREA)
    @property
    def destination_area(self):
        return self._details.get(AlgoField.DESTINATION_AREA)
    @property
    def additional_meters(self):
        return self._details.get(AlgoField.ADDITIONAL_METERS)
    @property
    def type(self):
        return self._details.get(AlgoField.PRICING_TYPE)
    @property
    def by_areas(self):
        return self.type == AlgoField.INTRACITY_AREAS


def get_parameters(extra=None):
    params = {
        'toleration_factor_minutes': SHARING_TIME_MINUTES,
        'toleration_factor_meters': SHARING_DISTANCE_METERS
    }

    if extra:
        params.update(extra)
    return params


def find_matches(candidate_rides, order_settings):
    payload = {
        AlgoField.RIDES : [serialize_shared_ride(r) for r in candidate_rides],
        "order"         : serialize_order_settings(order_settings),
        "parameters"    : get_parameters(extra={"debug": order_settings.debug})
    }

    payload = simplejson.dumps(payload)
    logging.info(u"submit=%s" % unicode(payload, "unicode-escape"))
    dt1 = datetime.now()
    response = safe_fetch(M2M_ENGINE_URL, payload="submit=%s" % payload, method=POST, deadline=50)
    dt2 = datetime.now()
    logging.info("response=%s" % response.content)

    matches = []
    if response and response.content:
        matches = simplejson.loads(response.content)[AlgoField.RIDES]

    logging.info("%s candidates [%s], %s matches (+1 new), %s seconds" % (len(candidate_rides),
                                                                ",".join([str(ride.id) for ride in candidate_rides]),
                                                                max(0, len(matches)-1),
                                                                (dt2 - dt1).seconds))

    return [RideData(match) for match in matches]


def recalc_ride(orders):
    """
    Calculate a shared ride from a list of orders
    """
    payload = {
        "orders": [serialize_order(o) for o in orders],
        "parameters": get_parameters()
    }

    payload = simplejson.dumps(payload)
    logging.info(u"recalc=%s" % unicode(payload, "unicode-escape"))
    response = safe_fetch(M2M_ENGINE_URL, payload="recalc=%s" % payload, method=POST, deadline=50)
    logging.info("response=%s" % response.content)

    if response and response.content:
        ride_data = simplejson.loads(response.content)[AlgoField.RIDES][0]
        return RideData(ride_data)

    return None


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


def get_pricing_area_name(lat, lng):
    name = ""

    pricing_area = CityArea.get_pricing_area(lat, lng)
    if pricing_area:
        name = pricing_area.name

    return name


def serialize_order(order):
    result = {
        "id": order.id,
        "num_seats": order.num_seats,
        "from_address": order.from_street_address,
        "from_area": get_pricing_area_name(order.from_lat, order.from_lon),
        "from_city": to_algo_city_name(order.from_city.name),
        "from_lat": order.from_lat,
        "from_lon": order.from_lon,
        "to_address": order.to_street_address,
        "to_area": get_pricing_area_name(order.to_lat, order.to_lon),
        "to_city": to_algo_city_name(order.to_city.name),
        "to_lat": order.to_lat,
        "to_lon": order.to_lon
    }

    return clean_values(result)


def serialize_order_settings(order_settings):
    result = {
        "id": NEW_ORDER_ID,
        "num_seats": order_settings.num_seats,
        "from_address": order_settings.pickup_address.formatted_address,
        "from_city": to_algo_city_name(order_settings.pickup_address.city_name),
        "from_area": get_pricing_area_name(order_settings.pickup_address.lat, order_settings.pickup_address.lng),
        "from_lat": order_settings.pickup_address.lat,
        "from_lon": order_settings.pickup_address.lng,
        "to_address": order_settings.dropoff_address.formatted_address,
        "to_city": to_algo_city_name(order_settings.dropoff_address.city_name),
        "to_area": get_pricing_area_name(order_settings.dropoff_address.lat, order_settings.dropoff_address.lng),
        "to_lat": order_settings.dropoff_address.lat,
        "to_lon": order_settings.dropoff_address.lng,
    }

    return clean_values(result)

def serialize_ride_point(ride_point):
    result = {
        AlgoField.TYPE: "e%s" % StopType.get_name(ride_point.type).title(),
        AlgoField.POINT_ADDRESS: {
            AlgoField.LAT: ride_point.lat,
            AlgoField.LNG: ride_point.lon,
            AlgoField.ADDRESS: ride_point.address,
            AlgoField.CITY: ride_point.city_name,
            AlgoField.AREA: get_pricing_area_name(ride_point.lat, ride_point.lon),
        },
        AlgoField.ORDER_IDS: [o.id for o in ride_point.orders]
    }

    return clean_values(result)

def serialize_shared_ride(ride):
    order_infos = {}
    for order in ride.orders.all():
        order_infos[order.id] = {
            'num_seats': order.num_seats,
            AlgoField.PRICE_SHARING_TARIFF1: order.price_data.for_tariff_type(TARIFFS.TARIFF1),
            AlgoField.PRICE_SHARING_TARIFF2: order.price_data.for_tariff_type(TARIFFS.TARIFF2)
        }

    result = {
        AlgoField.RIDE_ID           : ride.id,
        AlgoField.RIDE_POINTS       : [serialize_ride_point(rp) for rp in sorted(ride.points.all(), key=lambda p: p.stop_time)],
        AlgoField.ORDER_INFOS       : order_infos,
        AlgoField.COST_LIST_TARIFF1 : ride.cost_data.for_tariff_type(TARIFFS.TARIFF1),
        AlgoField.COST_LIST_TARIFF2 : ride.cost_data.for_tariff_type(TARIFFS.TARIFF2)
    }
    return clean_values(result)