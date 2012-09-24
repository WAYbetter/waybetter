from __future__ import absolute_import # we need absolute imports since ordering contains pricing.py

import logging
import traceback
from django.http import HttpResponseBadRequest
from django.utils.translation import get_language_from_request
from django.views.decorators.csrf import csrf_exempt
from common.tz_support import to_js_date, default_tz_now, set_default_tz_time
from common.util import first, Enum
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from django.conf import settings
from djangotoolbox.http import JSONResponse
from ordering.decorators import passenger_required, passenger_required_no_redirect
from ordering.models import SharedRide, NEW_ORDER_ID, RidePoint, StopType, Order, OrderType, ACCEPTED, APPROVED, PENDING, TARIFFS
from pricing.models import RuleSet
from sharing.algo_api import AlgoField
import simplejson
import datetime
import dateutil.parser

import sharing.algo_api as algo_api

MAX_SEATS = 3

def staff_m2m(request):
    return render_to_response("staff_m2m.html", RequestContext(request))


def get_ongoing_ride_details(request):
    order_id = request.GET.get("order_id")
    order = Order.by_id(order_id)

    response = { "success": False }

    if order:
        response["pickup_position"] = { "lat": order.from_lat, "lng": order.from_lon }
        response["station"] = { "name": order.ride.station.name, "phone": order.ride.station.phone }
        response["stops"] = [ {"lat": p.lat, "lng": p.lon}  for p in order.ride.pickup_points]
        response["success"] = True

    return JSONResponse(response)


def get_ongoing_order(passenger):
    """
    @param passenger:
    @return: ongoing order or None
    """
    delta = default_tz_now() - datetime.timedelta(minutes=15)
    ongoing_orders = list(passenger.orders.filter(depart_time__gt=delta).order_by("-depart_time"))
    ongoing_order = first(lambda o: o.status in [ACCEPTED, APPROVED, PENDING], ongoing_orders)
    return ongoing_order

@passenger_required_no_redirect
def sync_app_state(request, passenger):
    logging.info(passenger)
    response = {}

    response["pickup_datetime_options"] = [to_js_date(default_tz_now()), to_js_date(default_tz_now() + datetime.timedelta(minutes=30)), to_js_date(default_tz_now() + datetime.timedelta(days=1))]
    ongoing_order = get_ongoing_order(passenger)
    if ongoing_order:
        response["ongoing_order_id"] = ongoing_order.id


    logging.info("get_initial_status: %s" % response)
    return JSONResponse(response)

def get_defaults(request):
    #TODO_WB:
    pass


def get_history_suggestions(request):
    #TODO_WB:
    pass


def get_times_for_ordering(request):
    #TODO_WB:
    pass


def get_candidate_rides(order_settings):
    """
    Get rides that might be a match for the given order_settings
    @param order_settings: C{OrderSettings}
    @return:
    """
    #TODO_WB: implement
    start_dt = set_default_tz_time(datetime.datetime(2012, 9, 24, 13, 30))
    candidates = SharedRide.objects.filter(create_date__gte=start_dt)
    candidates = filter(lambda ride: ride.debug, candidates)
    candidates = filter(lambda ride: sum([order.num_seats for order in ride.orders.all()]) < 3, candidates)

    return candidates


def get_matching_rides(candidate_rides, order_settings):
    """
    Get matching rides for the given order_settings out of the candidate_rides

    @param candidate_rides:
    @param order_settings:
    @return: A list of JSON objects representing modified SharedRides
    """

    matches = algo_api.find_matches(candidate_rides, order_settings)
    return matches


def filter_matching_rides(matching_rides):
    """
    @param matching_rides: A list of JSON objects representing modified SharedRides returned by algorithm
    @return: A filtered list of JSON objects representing modified SharedRides
    """

    #TODO_WB: implement, TBD
    return matching_rides


def get_ride_cost_data_from(ride_data):
    return {TARIFFS.TARIFF1: (ride_data[AlgoField.COST_LIST_TARIFF1]),
             TARIFFS.TARIFF2: (ride_data[AlgoField.COST_LIST_TARIFF2])}

def get_order_price_data_from(ride_data, order_id=NEW_ORDER_ID):
    order_info = ride_data[AlgoField.ORDER_INFOS][str(order_id)]
    return {
        TARIFFS.TARIFF1: order_info[AlgoField.PRICE_SHARING_TARIFF1],
        TARIFFS.TARIFF2: order_info[AlgoField.PRICE_SHARING_TARIFF2]
    }


def get_offers(request):
    order_settings = OrderSettings.fromRequest(request)
    candidate_rides = get_candidate_rides(order_settings)
    matching_rides = get_matching_rides(candidate_rides, order_settings)
    filtered_rides = filter_matching_rides(matching_rides)

    offers = []
    tariffs = RuleSet.objects.all()

    for ride_data in filtered_rides:
        ride_id = ride_data[AlgoField.RIDE_ID]
        ride = SharedRide.by_id(ride_id)

        # get price for offer according to tariff
        price = None
        for tariff in tariffs:
            if tariff.is_active(order_settings.pickup_dt.date(), order_settings.pickup_dt.time()):
                price = get_order_price_data_from(ride_data).get(tariff.tariff_type)
                break
        if not price:
            logging.warning("get_offers missing price for %s" % order_settings.pickup_dt)
            continue


        if ride_id == NEW_ORDER_ID:
            offer = {
                "pickup_time": to_js_date(order_settings.pickup_dt),
                "price": price,
                "seats_left": MAX_SEATS,
                "new_ride": True,
            }

        else:
            pickup_point = first(lambda p: NEW_ORDER_ID in p[AlgoField.ORDER_IDS] and p[AlgoField.TYPE] == AlgoField.PICKUP, ride_data[AlgoField.RIDE_POINTS])
            offer = {
                "ride_id": ride_id,
                "pickup_time": to_js_date(ride.depart_time + datetime.timedelta(seconds=pickup_point[AlgoField.OFFSET_TIME])),
                "points": ["%s %s" % (p.stop_time.strftime("%H:%M"), p.address) for p in ride.points.all()],
                "seats_left": MAX_SEATS - sum([order.num_seats for order in ride.orders.all()]),
                "price": price,
                "new_ride": False,
            }

        offers.append(offer)

    return JSONResponse(offers)


@csrf_exempt
@passenger_required_no_redirect
def book_ride(request, passenger):
    order_settings = OrderSettings.fromRequest(request)
    logging.info("pikcup_dt: %s" % order_settings.pickup_dt)

    request_data = simplejson.loads(request.POST.get('data'))
    ride_id = int(request_data.get("ride_id", NEW_ORDER_ID))
    is_private = bool(request_data["settings"]["private"])

    if is_private:
        response = book_private_ride(order_settings, passenger)
    else:
        response = book_shared_ride(ride_id, order_settings, passenger)

    return response

def book_private_ride(order_settings, passenger):
    pass


def book_shared_ride(ride_id, order_settings, passenger):
    ride = SharedRide.by_id(ride_id)

    # get ride data from algo
    candidates = [ride] if ride else []
    matching_rides = get_matching_rides(candidates, order_settings)
    ride_data = first(lambda match: match[AlgoField.RIDE_ID] == ride_id, matching_rides)

    response = {'success': False}

    if not ride_data:
        return JSONResponse(response)

    order = Order.fromOrderSettings(order_settings, passenger, commit=False)
    order.type = OrderType.SHARED

    if ride_id == NEW_ORDER_ID:
        ride = create_shared_ride_for_order(ride_data, order)
        response['success'] = True

    elif ride.lock(): # try joining existing ride
        try:
            update_ride_for_order(ride, ride_data, order)
            ride.unlock()
            response['success'] = True
            #TODO_WB: notify passengers their price dropped

        except Exception as e:
            logging.error(traceback.format_exc())
            ride.unlock()

    if response['success']:
        response['ride'] = {
            'ride_id': ride.id,
            'price': order.price,
            'stops': ["%s %s" % (p.stop_time.strftime("%H:%M"), p.address) for p in ride.points.all()]
        }

    return JSONResponse(response)

def create_shared_ride_for_order(ride_data, order):
    ride = SharedRide()
    ride.depart_time = order.depart_time
    ride.debug = order.debug
    ride.arrive_time = ride.depart_time + datetime.timedelta(seconds=ride_data[AlgoField.REAL_DURATION])
    ride.cost_data = get_ride_cost_data_from(ride_data)
    ride.save()

    for point_data in ride_data[AlgoField.RIDE_POINTS]:
        create_ride_point(ride, point_data)

    for p in ride.points.all():
        if p.type == StopType.PICKUP:
            order.pickup_point = p
        else:
            order.dropoff_point = p

    order.ride = ride

    order.price_data = get_order_price_data_from(ride_data)
    order.save()

    return ride

def update_ride_for_order(ride, ride_data, new_order, depart_time=None):
    if not depart_time:
        #TODO_WB: decide what is the correct depart time
        depart_time = ride.depart_time

    orders = ride.orders.all()
    new_order_points = {
        AlgoField.PICKUP: None,
        AlgoField.DROPOFF: None
    }

    ride_points_data = ride_data[AlgoField.RIDE_POINTS]

    # update order prices and stop times of existing points
    for order in orders:
        order.price_data = get_order_price_data_from(ride_data, order.id)
        order.save()

        pickup_point = order.pickup_point
        dropoff_point = order.dropoff_point

        for point_data in ride_points_data:
            order_ids = point_data[AlgoField.ORDER_IDS]
            ptype = point_data[AlgoField.TYPE]
            offset = point_data[AlgoField.OFFSET_TIME]

            if order.id in order_ids:
                if ptype == AlgoField.PICKUP:
                    p = pickup_point
                else:
                    p = dropoff_point

                p.stop_time = depart_time + datetime.timedelta(seconds=offset)
                p.save()

                if NEW_ORDER_ID in order_ids:
                    new_order_points[ptype] = p


    # update stop times or create points for the new order
    for point_data in ride_points_data:
        ptype = point_data[AlgoField.TYPE]
        order_ids = point_data[AlgoField.ORDER_IDS]

        if NEW_ORDER_ID in order_ids:
            if len(order_ids) == 1:  # new point
                p = create_ride_point(ride, point_data)
            else:
                p = new_order_points[ptype]

            if p.type == StopType.PICKUP:
                new_order.pickup_point = p
            else:
                new_order.dropoff_point = p

    new_order.ride = ride
    new_order.price_data = get_order_price_data_from(ride_data)
    new_order.save()

    ride.cost_data = get_ride_cost_data_from(ride_data)
    ride.save()


def create_ride_point(ride, point_data):
    point = RidePoint()
    point.type = StopType.PICKUP if point_data[AlgoField.TYPE] == AlgoField.PICKUP else StopType.DROPOFF
    point.lon = point_data[AlgoField.POINT_ADDRESS][AlgoField.LNG]
    point.lat = point_data[AlgoField.POINT_ADDRESS][AlgoField.LAT]
    point.address = point_data[AlgoField.POINT_ADDRESS][AlgoField.NAME]
    point.stop_time = ride.depart_time + datetime.timedelta(seconds=point_data[AlgoField.OFFSET_TIME])
    point.ride = ride
    point.save()

    return point

# ==============
# HELPER CLASSES
# ==============
class AddressType(Enum):
    STREET_ADDRESS = 0
    POI = 1


class OrderSettings:
    pickup_address = None # Address instance
    dropoff_address = None # Address instance

    num_seats = 1
    pickup_dt = None # datetime
    luggage = False
    private = False # TODO_WB: replace with order type?
    debug = False

    language_code = settings.LANGUAGE_CODE
    user_agent = None
    mobile = None

    def __init__(self, num_seats=1, pickup_address=None, dropoff_address=None, pickup_dt=None, luggage=False,
                 private=False, debug=False):
        # TODO_WB: add validations
        self.num_seats = num_seats
        self.pickup_address = pickup_address
        self.dropoff_address = dropoff_address
        self.pickup_dt = pickup_dt
        self.luggage = luggage
        self.private = private
        self.debug = debug

    @classmethod
    def fromRequest(cls, request):
        request_data = simplejson.loads(request.REQUEST.get("data"))

        pickup = request_data.get("pickup")
        dropoff = request_data.get("dropoff")
        settings = request_data.get("settings")

        inst = cls()
        inst.num_seats = int(settings["num_seats"])
        inst.debug = bool(settings["debug"])
        inst.pickup_dt = dateutil.parser.parse(request_data.get("pickup_dt"))
        inst.pickup_address = Address(**pickup)
        inst.dropoff_address = Address(**dropoff)

        inst.mobile = request.mobile
        inst.language_code = request.POST.get("language_code", get_language_from_request(request))
        inst.user_agent = request.META.get("HTTP_USER_AGENT")

        return inst

    def serialize(self):
        return {
            "from_address": self.pickup_address.formatted_address,
            "from_lat": self.pickup_address.lat,
            "from_lon": self.pickup_address.lng,
            "to_address": self.dropoff_address.formatted_address,
            "to_lat": self.dropoff_address.lat,
            "to_lon": self.dropoff_address.lng,
            "num_seats": self.num_seats,
            "id": NEW_ORDER_ID
        }


class Address:
    lat = 0.0
    lng = 0.0
    house_number = None
    street = ""
    city_name = ""
    country_code = ""
    description = ""
    address_type = None

    def __init__(self, lat, lng, house_number=None, street=None, city_name=None, description=None, country_code=None,
                 address_type=AddressType.STREET_ADDRESS, **kwargs):
        self.lat = float(lat)
        self.lng = float(lng)

        self.house_number = house_number
        self.street = street
        self.city_name = city_name
        self.description = description
        self.country_code = country_code
        self.address_type = address_type

    @classmethod
    def from_order(cls, order, address_type):
        new_address = None
        try:
            new_address = Address(
                        getattr(order, "%s_lat" % address_type),
                        getattr(order, "%s_lon" % address_type),
                        house_number=getattr(order, "%s_house_number" % address_type),
                        street=getattr(order, "%s_street_address" % address_type),
                        city_name=getattr(order, "%s_city" % address_type).name,
                        description=getattr(order, "%s_raw" % address_type),
                        country_code=getattr(order, "%s_country" % address_type).code
                    )
        except AttributeError, e:
            pass
        return new_address


    @property
    def formatted_address(self):
        return u"%s %s, %s" % (self.street, self.house_number, self.city_name)

    def __eq__(self, other):
        return self.__hash__() == other.__hash__()

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return self.formatted_address.__hash__()

