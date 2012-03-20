import random
from ordering.models import Order
import logging
from fleet.backends.isr import ISR

def create_order():
    idx = random.randrange(1, 30)
    logging.info("random idx: %s" % idx)
    order = Order.objects.filter(debug=True)[idx]

#    order = Order.by_id(5224)
#    order.id = 646224
    return ISR.create_order(order)


def cancel_order(order_id):
    order = Order.by_id(order_id)
    return ISR.cancel_order(order)


def get_order_status(order_id):
    order = Order.by_id(order_id)
    return ISR.get_order_status(order)


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
