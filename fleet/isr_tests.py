import random
from django.contrib.auth.models import User
from django.conf import settings
from common.geocode import gmaps_geocode as _geocode
from common.models import City
from ordering.models import Order
import logging
from fleet.backends.isr import ISR

def create_order(address):
    if not address:
        return "Please choose a valid street address: street, house number and city"

    lat, lon, city, street, house_number = None, None, None, None, None
    results = _geocode(address, lang_code="he")
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

    if settings.LOCAL:
        user = User.objects.get(username="waybetter_admin")
    else:
        user = User.objects.get(username="isr_tester@waybetter.com")

    order = Order()
    order.id = random.randrange(1, 999999)
    order.from_raw = address
    order.from_city = city
    order.from_street_address = street
    order.from_house_number = house_number
    order.from_lat = lat
    order.from_lon = lon
    order.passenger = user.passenger

    return ISR.create_order(order)


def cancel_order(order_id):
    order = Order.by_id(order_id)
    return ISR.cancel_order(order)


def get_order_status(order_id):
    reply = ISR._get_client().service.Get_External_Order(ISR._get_login_token(), order_id)
    status = reply.Get_External_OrderResult.Status
    return status


def server_server_timestamp():
    return ISR._get_client().service.Server_Server_TimeStamp()


def server_server_version():
    return ISR._get_client().service.Server_Server_Version()


def server_session_id():
    return ISR._get_client().service.Server_Session_ID()


def server_test():
    return ISR._get_client().service.Server_Test()


def login():
    return ISR._get_client().service.Login(ISR.USERNAME, ISR.PASSWORD)


def get_taxi_recommendation():
    """
    for a random order
    """
    order = Order.get_one()
    max_radius = 1000
    max_vehicles = 2
    return ISR._get_client().service.Get_Taxi_Recommendation(ISR._get_login_token(), float(order.from_lat),
        float(order.from_lon), max_radius, max_vehicles)


def get_available_operators():
    return ISR._get_client().service.Get_Available_Operators(ISR._get_login_token())
