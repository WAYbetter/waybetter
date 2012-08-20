from datetime import timedelta
import enum
import simplejson
from common.util import first, Enum
from django.shortcuts import render_to_response
from djangotoolbox.http import JSONResponse
from ordering.models import SharedRide, SHARING_TIME_MINUTES, SHARING_DISTANCE_METERS
from sharing.algo_api import AlgoField

NEW_ORDER_ID = 0

def staff_m2m(request):
    return render_to_response("staff_m2m.html")

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
    return SharedRide.objects.all()[0:3]

def get_matching_rides(candidate_rides, order_settings):
    """
    Get matching rides for the given order_settings out of the candidate_rides

    @param candidate_rides:
    @param order_settings:
    @return: A list of JSON objects representing modified SharedRides
    """

    request_data = {
        AlgoField.RIDES : [r.serialize_for_algo() for r in candidate_rides],
        "order"         : order_settings.serialize(),
        "parameters"    : {
            "debug"                     : order_settings.debug,
            'toleration_factor_minutes' : SHARING_TIME_MINUTES,
            'toleration_factor_meters'  : SHARING_DISTANCE_METERS
        }
    }

    json = simplejson.dumps(request_data)

    response = """[
      {
        "m_RideID": 121312313,
        "m_Price": 37.925,
        "m_OrderInfos": {
          "0": {
            "m_TimeSharing": 1153.0,
            "m_DistSharing": 0.0,
            "m_SuggestedPriceWeight": 100.0,
            "m_TimeAlone": 1153.0,
            "m_TotalDuration": 0.0,
            "m_DistanceAddition": 0.0,
            "m_DistanceMultiplier": 1.0,
            "m_DurationAddition": 0.0,
            "m_DistAlone": 5989.0,
            "m_PriceAlone": 37.925,
            "m_DurationMultiplier": 1.0,
            "m_EstimatedDuration": 1153.0,
            "num_seats": 1,
            "m_TotalDistance": 0.0,
            "m_PriceSharing": 37.925
          }
        },
        "m_CarType": {
          "cost_multiplier": 1.0,
          "max_passengers": 3
        },
        "m_Duration": 1153.0,
        "m_RidePoints": [
          {
            "m_OrderIDs": [
              0
            ],
            "m_offset_time": 0.0,
            "m_PointAddress": {
              "m_Latitude": 32.108737,
              "m_Longitude": 34.83917,
              "m_Name": "\\u05d4\\u05d1\\u05e8\\u05d6\\u05dc 21 -\\u05d1\'\\u05db\\u05d9\\u05db\\u05e8\', \\u05ea\\u05dc \\u05d0\\u05d1\\u05d9\\u05d1 \\u05d9\\u05e4\\u05d5"
            },
            "m_Type": "ePickup"
          },
          {
            "m_OrderIDs": [
              0
            ],
            "m_offset_time": 1153.0,
            "m_PointAddress": {
              "m_Latitude": 32.0983429,
              "m_Longitude": 34.798402399999986,
              "m_Name": "\\u05d4\\u05e8\\u05d1 \\u05e7\\u05d5\\u05e1\\u05d5\\u05d1\\u05e1\\u05e7\\u05d9 38, \\u05ea\\u05dc \\u05d0\\u05d1\\u05d9\\u05d1 \\u05d9\\u05e4\\u05d5"
            },
            "m_Type": "eDropoff"
          }
        ],
        "m_TotalDistance": 5989.0
      }
    ]"""
    #TODO_WB: do actual call

    return simplejson.loads(response)

def filter_matching_rides(matching_rides):
    """
    @param matching_rides: A list of JSON objects representing modified SharedRides returned by algorithm
    @return: A filtered list of JSON objects representing modified SharedRides
    """

    #TODO_WB: implement, TBD
    return matching_rides

def get_offers(request):
    order_settings = OrderSettings.fromRequest(request)
    candidate_rides = get_candidate_rides(order_settings)
    matching_rides = get_matching_rides(candidate_rides, order_settings)
    filtered_rides = filter_matching_rides(matching_rides)

    offers = []

    for ride in filtered_rides:
        pickup_point = first(lambda p: NEW_ORDER_ID in p[AlgoField.ORDER_IDS] and p[AlgoField.TYPE] == AlgoField.PICKUP, ride[AlgoField.RIDE_POINTS])
        offers.append({
                "price": ride[AlgoField.ORDER_INFOS][NEW_ORDER_ID][AlgoField.PRICE_SHARING],
                "time": order_settings.pickup_dt + timedelta(seconds=pickup_point[AlgoField.OFFSET_TIME])
        })

    return JSONResponse(offers)

def book_ride(request):

    def _do_book_ride(ride_id, modified_ride, order_settings):
        # create an Order from order_settings and save it
        # connect the order to the ride
        # create ride points and connect to ride
        # save ride

        return False

    ride_id = request.POST.get("ride_id")
    modify_date = request.POST.get("ride_modify_date")
    order_settings = OrderSettings.fromRequest(request)

    if ride_id:
        ride = SharedRide.by_id(ride_id)
         # query algo for matches again to get the modified version of the ride the user wish to join
        matching_rides = get_matching_rides([ride], order_settings)
        modified_ride = first(lambda match: match.id == ride.id, matching_rides)

        if modified_ride and ride.lock():
            _do_book_ride(ride_id, modified_ride, order_settings)
            ride.unlock()
            #TODO_WB: handle success
            pass
        else:
            #TODO_WB: handle failure - ride can NOT be joined
            pass

# ==============
# HELPER CLASSES
# ==============
class AddressType(Enum):
    STREET_ADDRESS = 0
    POI = 1

class OrderSettings:
    num_seats = 1
    pickup_address = None
    dropoff_address = None
    pickup_dt = None # datetime
    luggage = False
    private = False
    debug = False

    @classmethod
    def fromRequest(cls, request):
        #TODO_WB: implement
        pass

    def __init__(self, num_seats=1, pickup_address=None, dropoff_address=None, pickup_dt=None, luggage=False, private=False, debug=False):
        self.num_seats = num_seats
        self.pickup_address = pickup_address
        self.dropoff_address = dropoff_address
        self.pickup_dt = pickup_dt
        self.luggage = luggage
        self.private = private
        self.debug = debug

    def serialize(self):
        return {
            "from_address": self.pickup_address.formatted_address(),
            "from_lat": self.pickup_address.lat,
            "from_lon": self.pickup_address.lng,
            "to_address": self.dropoff_address.formatted_address(),
            "to_lat": self.dropoff_address.lat,
            "to_lon": self.dropoff_address.lng,
            "num_seats": self.num_seats,
            "private": self.private,
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

    def __init__(self, lat, lng, house_number=None, street=None, city_name=None, description=None, country_code=None, address_type=AddressType.STREET_ADDRESS):
        self.lat = float(lat)
        self.lng = float(lng)

        self.house_number = house_number
        self.street = street
        self.city_name= city_name
        self.description = description
        self.country_code = country_code
        self.address_type = address_type

    @property
    def formatted_address(self):
        return u"%s %s" % (self.street, self.house_number)


