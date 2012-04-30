import random
import datetime
from django.contrib.auth.models import User
from common.models import City
from fleet import fleet_manager
from fleet.models import FleetManager
from ordering.models import Order, Passenger, Station, ASSIGNED
from fleet.backends.isr import ISR
from fleet.backends.isr_proxy import ISRProxy

BACKEND = ISRProxy
#BACKEND = ISR

isrproxy_fm = FleetManager.objects.get(name="isrproxy")
class FakeOrdersManager(object):
    def __init__(self, orders):
        self.orders = list(orders)

    def all(self):
        return self.orders

class FakeSharedRide(object):
    def __init__(self, orders):
        self.orders = FakeOrdersManager(orders)


def create_ride(address, comments, passenger_phone, first_name, last_name, start_time, finish_time, station_id, as_raw_output):
    from common.tz_support import set_default_tz_time
    from common.geocode import gmaps_geocode

    if not address:
        return "Please choose a valid street address: street, house number and city"

    lat, lon, city, street, house_number = None, None, None, None, None
    results = gmaps_geocode(address, lang_code="he")
    if results:
        result = results[0]
        if "street_address" in result["types"]:
            lat = result["geometry"]["location"]["lat"]
            lon = result["geometry"]["location"]["lng"]

            for component in result["address_components"]:
                if "street_number" in component["types"]:
                    house_number = component["short_name"]
                if "route" in component["types"]:
                    street = component["short_name"]
                if "locality" in component["types"]:
                    city_name = component["short_name"]
                    city = City.objects.get(name=city_name)

    if not all([lat, lon, city, street, house_number]):
        return "Please choose a valid street address: street, house number and city"

    user = User()
    user.first_name = first_name
    user.last_name = last_name

    passenger = Passenger()
    passenger.user = user
    passenger.phone = passenger_phone
    passenger.id = random.randrange(1, 999999)

    order = Order()
    order.id = random.randrange(1, 999999)
    order.from_raw = address
    order.from_city = city
    order.from_street_address = street
    order.from_house_number = house_number
    order.from_lat = lat
    order.from_lon = lon
    order.comments = comments
    order.depart_time = set_default_tz_time(datetime.datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%S")) if start_time else None
    order.arrive_time = set_default_tz_time(datetime.datetime.strptime(finish_time, "%Y-%m-%dT%H:%M:%S")) if finish_time else None
    order.passenger = passenger

    station = Station()
    station.fleet_manager = isrproxy_fm
    station.fleet_station_id = station_id or 8 # waybetter station operator id

    ride = FakeSharedRide([order])
    ride.id = random.randrange(1, 999999)
    ride.station = station
    ride.dn_fleet_manager_id = isrproxy_fm.id
    ride.status = ASSIGNED

    fleet_manager.DEV_WB_ONGOING_RIDES.append(ride)

    if as_raw_output:
        ex_order = ISR._create_external_order(order, station)
        reply = ISR._get_client().service.Insert_External_Order(ISR._get_login_token(), ex_order)
        return reply

    return fleet_manager.create_ride(ride)
#    return BACKEND.create_ride(ride, station)

def cancel_ride(ride_id):
    ride = FakeSharedRide([])
    ride.id = ride_id
    ride.dn_fleet_manager_id = isrproxy_fm.id

    return fleet_manager.cancel_ride(ride_id)
#    return BACKEND.cancel_ride(ride_id)

def get_ride(ride_id, as_raw_output):
    if as_raw_output:
        return ISR._get_client().service.Get_External_Order(ISR._get_login_token(), ride_id)
    return BACKEND.get_ride(ride_id)

def get_ongoing_rides():
    fmrs = ISR.get_ongoing_rides()
    if fmrs:
        return [fmr.id for fmr in fmrs]
    else:
        return "No ongoing rides"

def get_var_supplier_orders(status_list):
    """
    enter int values separated by ","
    """
    array_of_int = ISR._create_array_object("ArrayOfint")
    array_of_int.int = status_list.split(",")
    return ISR._get_client().service.Get_VAR_Supplier_Orders(ISR._get_login_token(), ISR._get_supplier_id(), array_of_int)

#def server_server_timestamp():
#    return ISR._get_client().service.Server_Server_TimeStamp()
#
#
#def server_server_version():
#    return ISR._get_client().service.Server_Server_Version()
#
#
def server_session_id():
    return ISR._get_client().service.Server_Session_ID()

#def server_test():
#    return ISR._get_client().service.Server_Test()
#
#
#def login():
#    return ISR._get_client().service.Login(ISR.USERNAME, ISR.PASSWORD)
#
#
#def get_taxi_recommendation():
#    """
#    for a random order
#    """
#    order = Order.get_one()
#    max_radius = 1000
#    max_vehicles = 2
#    return ISR._get_client().service.Get_Taxi_Recommendation(ISR._get_login_token(), float(order.from_lat),
#        float(order.from_lon), max_radius, max_vehicles)
#
#
def get_available_operators():
    return ISR._get_client().service.Get_Available_Operators(ISR._get_login_token())
