from django.utils.translation import ugettext_noop
from ordering.signals import   SignalType
from ordering.util import send_msg_to_passenger
from common.signals import AsyncSignal
from common.decorators import  receive_signal
from common.langsupport.util import translate_to_lang
from ordering.models import Order, OrderAssignment, FAILED, ACCEPTED, PENDING, ASSIGNED, ERROR, TIMED_OUT
import datetime
import logging

STATUS_MESSAGES = {
    PENDING: ugettext_noop("Sending order"),
    ASSIGNED: ugettext_noop("Searching for taxi"),
    ACCEPTED: ugettext_noop("Taxi on its way"),
    FAILED: ugettext_noop("Sorry, we could not find a taxi for you :(")
}

@receive_signal(*AsyncSignal.all)
def order_tracker(sender, signal_type, obj, **kwargs):
    '''
    Handler for all async signals
    Sends messages to passenger's channel
    '''
    if signal_type in [SignalType.ASSIGNMENT_CREATED, SignalType.ASSIGNMENT_STATUS_CHANGED]:
        order_assignment = obj

        if order_assignment.status in [PENDING, ASSIGNED]:
            order = order_assignment.order
            passenger = order.passenger

            # change this when tracker used for all passengers
            if passenger.business:
                msg = get_tracker_msg_for_order(order, last_assignment=order_assignment)
                send_msg_to_passenger(passenger, msg)
            else:
                return

    elif signal_type in [SignalType.ORDER_STATUS_CHANGED]:
        order = obj

        if order.status in [ACCEPTED, TIMED_OUT, FAILED, ERROR]:
            passenger = order.passenger

            # change this when tracker used for all passengers
            if passenger.business:
                msg = get_tracker_msg_for_order(order)
                send_msg_to_passenger(passenger, msg)
            else:
                return


def get_tracker_msg_for_order(order, last_assignment=None):
    msg = {}

    # new order, still pending
    if order.status == PENDING:
        msg.update({"pk": order.id,
                    "status": PENDING,
                    "from_raw": order.from_raw,
                    "to_raw": order.to_raw,
                    })

    # order is assigned, get status from the most recent assignment
    elif order.status == ASSIGNED:
        if not last_assignment:
            try:
                last_assignment = OrderAssignment.objects.filter(order=order).order_by('-create_date')[0]
            except IndexError:
                logging.error("tracker msg error: cannot get last assignment of order %d" % order.id)

        if last_assignment and last_assignment.status in [PENDING, ASSIGNED]:
            msg.update({"pk": order.id,
                        "status": last_assignment.status,
                        "from_raw": order.from_raw,
                        "to_raw": order.to_raw,
                        "info": translate_to_lang(STATUS_MESSAGES[last_assignment.status], order.language_code),
                        "station": last_assignment.station.name,
                        })

    # order has final status
    elif order.status == ACCEPTED:
        pickup_hour = order.modify_date + datetime.timedelta(minutes=order.pickup_time)
        msg.update({"pk": order.id,
                    "status": ACCEPTED,
                    "from_raw": order.from_raw,
                    "to_raw": order.to_raw,
                    "info": translate_to_lang(STATUS_MESSAGES[ACCEPTED], order.language_code),
                    "station": order.station_name,
                    "station_phone": str(order.station.phones.all()[0]),
                    "pickup_time_sec": order.get_pickup_time(),
                    "pickup_hour": pickup_hour.strftime("%H:%M"),
                    })

    elif order.status in [TIMED_OUT, FAILED, ERROR]:
        msg.update({"pk": order.id,
                    "status": FAILED,
                    "from_raw": order.from_raw,
                    "to_raw": order.to_raw,
                    "info": translate_to_lang(STATUS_MESSAGES[FAILED], order.language_code),
                    })

    return msg

def get_tracker_history(passenger):
    # 1. currently active orders
    active_orders_qs = Order.objects.filter(passenger=passenger, status__in=[ASSIGNED])
    active_orders = [get_tracker_msg_for_order(order) for order in active_orders_qs]

    # 2. orders with future pickup
    future_pickup_orders = Order.objects.filter(passenger=passenger, future_pickup=True)
    future_orders_by_pickup = [] # (pickup, msg) pairs
    for order in future_pickup_orders:
        pickup = order.get_pickup_time()
        msg = get_tracker_msg_for_order(order)
        future_orders_by_pickup.append((pickup, msg))
    future_orders_by_pickup = [order[1] for order in
                               sorted(future_orders_by_pickup, reverse=True, key=lambda item: item[0])]
    # 3. recently failed orders
    recent_time_delta = datetime.datetime.now() - datetime.timedelta(minutes=10)
    recent_failed_orders_qs = Order.objects.filter(create_date__gt=recent_time_delta, passenger=passenger,
                                                   status__in=[ERROR, FAILED, TIMED_OUT])
    recent_failed_orders = [get_tracker_msg_for_order(order) for order in recent_failed_orders_qs]


    return filter(None, recent_failed_orders + future_orders_by_pickup + active_orders) # <-- this side up
