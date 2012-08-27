import logging
import traceback
from django.http import HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from common.tz_support import to_js_date, default_tz_now, set_default_tz_time
from common.util import first, Enum
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from djangotoolbox.http import JSONResponse
from ordering.decorators import passenger_required
from ordering.models import SharedRide, NEW_ORDER_ID, RidePoint, StopType, Order
from sharing.algo_api import AlgoField
import simplejson
import datetime
import dateutil.parser

#import sharing.mock_algo_api as algo_api
import sharing.algo_api as algo_api

def staff_m2m(request):
    return render_to_response("staff_m2m.html", RequestContext(request))


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
    start_dt = set_default_tz_time(datetime.datetime(2012, 8, 27, 15, 15))
    return SharedRide.objects.filter(create_date__gte=start_dt)


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


##TODO_WB: remove csrf?
@csrf_exempt
def get_offers(request):
    order_settings = OrderSettings.fromRequestData(simplejson.loads(request.GET.get("data")))
    candidate_rides = get_candidate_rides(order_settings)
    matching_rides = get_matching_rides(candidate_rides, order_settings)
    filtered_rides = filter_matching_rides(matching_rides)

    offers = []

    for ride_data in filtered_rides:
        ride_id = ride_data[AlgoField.RIDE_ID]
        ride = SharedRide.by_id(ride_id)

        price = ride_data[AlgoField.ORDER_INFOS][str(NEW_ORDER_ID)][AlgoField.PRICE_SHARING]
        if ride_id == NEW_ORDER_ID:
            offer = {
                "pickup_time": to_js_date(order_settings.pickup_dt),
                "ride_depart_time": to_js_date(order_settings.pickup_dt),
                "price": price,
                "seats_taken": 0,
            }

        else:
            pickup_point = first(lambda p: NEW_ORDER_ID in p[AlgoField.ORDER_IDS] and p[AlgoField.TYPE] == AlgoField.PICKUP, ride_data[AlgoField.RIDE_POINTS])
            offer = {
                "ride_id": ride_id,
                "pickup_time": to_js_date(order_settings.pickup_dt + datetime.timedelta(seconds=pickup_point[AlgoField.OFFSET_TIME])),
                "ride_depart_time": to_js_date(ride.depart_time),
                "points": ["%s %s" % (p.stop_time.strftime("%H:%M"), p.address) for p in ride.points.all()],
                "seats_taken": sum([order.num_seats for order in ride.orders.all()]),
                "price": price,
            }

        offers.append(offer)

    return JSONResponse(offers)


##TODO_WB: remove csrf?
@csrf_exempt
@passenger_required
def book_ride(request, passenger):
    booking_data = simplejson.loads(request.raw_post_data)
    #TODO_WB: add missing order fields: language_code, mobile, user_agent, etc.

    if booking_data["settings"]["private"]:
        response = book_private_ride(booking_data, passenger)
    else:
        response = book_shared_ride(booking_data, passenger)

    return response

def book_private_ride(booking_data, passenger):
    pass


def book_shared_ride(booking_data, passenger):
    ride_id = int(booking_data.get("ride_id", NEW_ORDER_ID))
    ride = SharedRide.by_id(ride_id)
    order_settings = OrderSettings.fromRequestData(booking_data)

    candidates = [ride] if ride else []
    matching_rides = get_matching_rides(candidates, order_settings) # will create ride from algo response
    ride_data = first(lambda match: match[AlgoField.RIDE_ID] == ride_id, matching_rides)

    if not ride_data:
        return HttpResponseBadRequest() # TODO_WB

    response = {'success': False}
    order = Order.fromOrderSettings(order_settings, passenger, commit=False)
    order.price = ride_data[AlgoField.ORDER_INFOS][str(NEW_ORDER_ID)][AlgoField.PRICE_SHARING]


    if ride_id == NEW_ORDER_ID:
        ride = create_shared_ride(ride_data, depart_time=order_settings.pickup_dt, debug=order_settings.debug)
        order.ride = ride
        for p in ride.points.all():
            if p.type == StopType.PICKUP:
                order.pickup_point = p
            else:
                order.dropoff_point = p
        order.save()
        response['success'] = True

    elif ride.lock(): # try joining existing ride
        try:
            update_shared_ride(ride, ride_data, order)
            ride.unlock()
            response['success'] = True

        except Exception as e:
            logging.error(traceback.format_exec())
            ride.unlock()

    if response['success']:
        response['ride'] = {
            'ride_id': ride.id,
            'price': order.price,
            'stops': ["%s %s" % (p.stop_time.strftime("%H:%M"), p.address) for p in ride.points.all()]
        }

    return JSONResponse(response)

def create_shared_ride(ride_data, depart_time, debug=False):
    ride = SharedRide()
    ride.depart_time = depart_time
    ride.debug = debug
    ride.arrive_time = ride.depart_time + datetime.timedelta(seconds=ride_data[AlgoField.REAL_DURATION])
    ride.save()

    for point_data in ride_data[AlgoField.RIDE_POINTS]:
        create_ride_point(ride, point_data)

    return ride

def update_shared_ride(ride, ride_data, new_order, depart_time=None):
    if not depart_time:
        #TODO_WB: decide what is the correct depart time
        depart_time = ride.depart_time

    orders = ride.orders.all()
    new_order_points = {
        AlgoField.PICKUP: None,
        AlgoField.DROPOFF: None
    }

    ride_points_data = ride_data[AlgoField.RIDE_POINTS]
    for order in orders:
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
    new_order.save()

    logging.info('ride %s updated' % ride.id)


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
    private = False
    debug = False

    def __init__(self, num_seats=1, pickup_address=None, dropoff_address=None, pickup_dt=None, luggage=False,
                 private=False, debug=False):
        self.num_seats = num_seats
        self.pickup_address = pickup_address
        self.dropoff_address = dropoff_address
        self.pickup_dt = pickup_dt
        self.luggage = luggage
        self.private = private
        self.debug = debug

    @classmethod
    def fromRequestData(cls, request_data):
        pickup = request_data.get("pickup")
        dropoff = request_data.get("dropoff")
        settings = request_data.get("settings")

        inst = cls()
        inst.num_seats = int(settings["num_seats"])
        inst.debug = bool(settings["debug"])
        inst.pickup_dt = dateutil.parser.parse(request_data.get("pickup_dt"))
        inst.pickup_address = Address(**pickup)
        inst.dropoff_address = Address(**dropoff)

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

    @property
    def formatted_address(self):
        return u"%s %s, %s" % (self.street, self.house_number, self.city_name)


