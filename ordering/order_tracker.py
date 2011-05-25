from django.utils.translation import ugettext as _
from django.utils import simplejson
from ordering.signals import   SignalType
from common.signals import AsyncSignal
from common.decorators import  receive_signal
from models import Order, OrderAssignment, FAILED, ACCEPTED, PENDING, ASSIGNED, ERROR, TIMED_OUT
import datetime

ugettext = lambda s: s # use dummy ugettext for makemessages
STATUS_MESSAGES = {
    PENDING: ugettext("Contacting..."),
    ASSIGNED: ugettext("Searching for taxi"),
    ACCEPTED: ugettext("Taxi on its way"),
    FAILED: ugettext("Sorry, we could not find a taxi for you :(")
}

@receive_signal(*AsyncSignal.all)
def order_tracker(sender, signal_type, obj, **kwargs):
    '''
    Handler for all async signals
    Sends messages to passenger's channel
    '''
    if signal_type in [SignalType.ASSIGNMENT_CREATED, SignalType.ASSIGNMENT_STATUS_CHANGED]:
        order_assignment = obj.fresh_copy()
        order = order_assignment.order
        passenger = order.passenger

        if not passenger.business:
            return

        msg = get_tracker_msg_for_order(order, last_assignment=order_assignment)
        if msg:
            passenger.send_channel_msg(msg)

    elif signal_type in [SignalType.ORDER_STATUS_CHANGED]:
        order = obj.fresh_copy()
        passenger = order.passenger

        if not passenger.business:
            return

        msg = get_tracker_msg_for_order(order)
        if msg:
            passenger.send_channel_msg(msg)


def get_tracker_msg_for_order(order, last_assignment=None):
    msg = {}

    # order has final status
    if order.status in [TIMED_OUT, FAILED, ERROR]:
        msg.update({"pk": order.id,
                    "status": FAILED,
                    "from_raw": order.from_raw,
                    "to_raw": order.to_raw,
                    "info": _(STATUS_MESSAGES[FAILED]),
                    })
    elif order.status == ACCEPTED:
        msg.update({"pk": order.id,
                    "status": ACCEPTED,
                    "from_raw": order.from_raw,
                    "to_raw": order.to_raw,
                    "info": _(STATUS_MESSAGES[ACCEPTED]),
                    "station": order.station_name,
                    "station_phone": str(order.station.phones.all()[0]),
                    "pickup_time_sec": order.get_pickup_time(),
                    })

    # order is still 'alive', get status from the most recent assignment
    else:
        if not last_assignment:
            try:
                last_assignment = OrderAssignment.objects.filter(order=order).order_by('-create_date')[0]
            except IndexError:
                return {}

        status = last_assignment.status
        if status in [PENDING, ASSIGNED]:
            msg.update({"pk": order.id,
                        "status": status,
                        "from_raw": order.from_raw,
                        "to_raw": order.to_raw,
                        "info": _(STATUS_MESSAGES[status]),
                        "station": last_assignment.station.name,
                        })

    if msg: # msg was updated with real content
        return simplejson.dumps(msg)
    else:
        return simplejson.dumps({"pk" : 0})

def get_tracker_history(passenger):
    # 1. currently active orders
    active_orders_qs = Order.objects.filter(passenger=passenger, status=ASSIGNED)
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


    return recent_failed_orders + future_orders_by_pickup + active_orders # <-- this side up