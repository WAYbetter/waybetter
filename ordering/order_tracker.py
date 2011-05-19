from django.utils import simplejson
from django.utils.translation import ugettext
from ordering.signals import   SignalType
from common.signals import AsyncSignal
from common.decorators import  receive_signal
from models import  OrderAssignment, FAILED, ACCEPTED, PENDING, ASSIGNED, ERROR, TIMED_OUT

STATUS_MESSAGES = {
    PENDING: ugettext("Waiting..."),
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
        order_assignment = obj
        order = order_assignment.order
        passenger = order.passenger

        if not passenger.business:
            return

        msg = get_tracker_msg_for_order(order, last_assignment=order_assignment)
        if msg:
            passenger.send_channel_msg(msg)

    elif signal_type in [SignalType.ORDER_STATUS_CHANGED]:
        order = obj
        passenger = order.passenger

        if not passenger.business:
            return

        msg = get_tracker_msg_for_order(order)
        if msg:
            passenger.send_channel_msg(msg)


def get_tracker_msg_for_order(order, last_assignment=None):
    msg = {"pk": "",
           "status": "",
           "from_raw": "",
           "to_raw": "",
           "info": "",
           "station": "",
           "station_phone": "",
           "pickup_time": "",
           }

    # order has final status
    if order.status in [TIMED_OUT, FAILED, ERROR]:
        msg.update({"pk": order.id,
                    "status": FAILED,
                    "from_raw": order.from_raw,
                    "to_raw": order.to_raw,
                    "info": STATUS_MESSAGES[FAILED],
                    })
    elif order.status == ACCEPTED:
        msg.update({"pk": order.id,
                    "status": ACCEPTED,
                    "from_raw": order.from_raw,
                    "to_raw": order.to_raw,
                    "info": STATUS_MESSAGES[ACCEPTED] if order.future_pickup else "",
                    "station": order.station.name,
                    "station_phone": order.station.phones.all()[0],
                    "pickup_time": order.get_pickup_time() if order.future_pickup else "",
                    })

    # order is still 'alive', get status from the most recent assignment
    else:
        if not last_assignment:
            try:
                last_assignment = OrderAssignment.objects.filter(order=order).order_by('-create_date')[0]
            except IndexError:
                return {}

        status = last_assignment.status
        if status in STATUS_MESSAGES.keys():
            msg.update({"pk": order.id,
                        "status": status,
                        "from_raw": order.from_raw,
                        "to_raw": order.to_raw,
                        "info": STATUS_MESSAGES[status],
                        "station": last_assignment.station.name,
                        "station_phone": order.station.phones.all()[0] if status == ACCEPTED else "",
                        "pickup_time": order.get_pickup_time() if order.future_pickup else "",
                        })

    if msg['pk']: # msg was updated with real content
        return simplejson.dumps(msg)
    else:
        return {}