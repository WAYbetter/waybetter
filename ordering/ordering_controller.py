from common.tz_support import to_js_date
from common.util import first, Enum
from django.shortcuts import render_to_response
from djangotoolbox.http import JSONResponse
from django.conf import settings
from ordering.models import SharedRide, NEW_ORDER_ID
from sharing.algo_api import AlgoField
import simplejson
import datetime
import dateutil.parser

if settings.DEV:
    import sharing.mock_algo_api as algo_api
else:
    import sharing.algo_api as algo_api

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
    return SharedRide.objects.all()[:5]


def get_matching_rides(candidate_rides, order_settings):
    """
    Get matching rides for the given order_settings out of the candidate_rides

    @param candidate_rides:
    @param order_settings:
    @return: A list of JSON objects representing modified SharedRides
    """

    response = algo_api.find_matches(candidate_rides, order_settings)
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
        pickup_point = first(lambda p: NEW_ORDER_ID in p[AlgoField.ORDER_IDS] and p[AlgoField.TYPE] == AlgoField.PICKUP,
                             ride[AlgoField.RIDE_POINTS])
        offers.append({
            "price": ride[AlgoField.ORDER_INFOS][str(NEW_ORDER_ID)][AlgoField.PRICE_SHARING],
            "time": to_js_date(order_settings.pickup_dt + datetime.timedelta(seconds=pickup_point[AlgoField.OFFSET_TIME]))
        })

    return JSONResponse(offers)


def book_ride(request):
    def _do_book_ride(ride_id, modified_ride, order_settings):
        #TODO_WB
        # create an Order from order_settings and save it
        # connect the order to the ride
        # create ride points and connect to ride
        # save ride

        return False

    ride_id = request.POST.get("ride_id")
    order_settings = OrderSettings.fromRequest(request)

    if ride_id:
        ride = SharedRide.by_id(ride_id)

        matching_rides = get_matching_rides([ride], order_settings) # query algo again for safety
        modified_ride = first(lambda match: match.id == ride.id, matching_rides)

        if modified_ride and ride.lock():
            try:
                _do_book_ride(ride_id, modified_ride, order_settings)
                ride.unlock()
                #TODO_WB: handle success
                pass
            except Exception as e:
                ride.unlock()
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
    def fromRequest(cls, request):
        pickup = simplejson.loads(request.GET.get("pickup"))
        dropoff = simplejson.loads(request.GET.get("dropoff"))
        settings = simplejson.loads(request.GET.get("settings"))

        inst = cls()
        inst.num_seats = int(settings["num_seats"])
        inst.debug = bool(settings["debug"])
        inst.pickup_dt = dateutil.parser.parse(request.GET.get("pickup_dt"))
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
        return u"%s %s" % (self.street, self.house_number)


