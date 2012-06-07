from common.decorators import receive_signal
from common.signals import AsyncSignal
from common.util import  Enum
import logging

class SignalType(Enum):
    ORDER_CREATED               = 1
    ORDER_STATUS_CHANGED        = 2
    ASSIGNMENT_CREATED          = 3
    ASSIGNMENT_STATUS_CHANGED   = 4
    WORKSTATION_ONLINE          = 5
    WORKSTATION_OFFLINE         = 6

order_created_signal                    = AsyncSignal(SignalType.ORDER_CREATED, providing_args=["obj"])
orderassignment_created_signal          = AsyncSignal(SignalType.ASSIGNMENT_CREATED, providing_args=["obj"])
orderassignment_status_changed_signal   = AsyncSignal(SignalType.ASSIGNMENT_STATUS_CHANGED, providing_args=["obj", "status"])
order_status_changed_signal             = AsyncSignal(SignalType.ORDER_STATUS_CHANGED, providing_args=["obj", "status"])

workstation_online_signal               = AsyncSignal(SignalType.WORKSTATION_ONLINE, providing_args=["obj"])
workstation_offline_signal              = AsyncSignal(SignalType.WORKSTATION_OFFLINE, providing_args=["obj"])

@receive_signal(order_status_changed_signal)
def handle_approved_orders(sender, signal_type, obj, status, **kwargs):
    from common.util import notify_by_email
    from ordering.models import StopType, OrderType, APPROVED
    from ordering.util import create_single_order_ride
    from sharing.algo_api import submit_to_prefetch
    from sharing import computation_manger

    if status == APPROVED:
        order = obj

        if order.type == OrderType.PRIVATE:
            ride = create_single_order_ride(order)

        elif order.type == OrderType.SHARED:
            computation = computation_manger.get_hotspot_computation(order)

            if computation:
                logging.info("order [%s] added to computation [%s] %s" % (order.id, computation.id, computation.key))
                order.computation = computation
                order.save()

                address_dir = "to" if order.hotspot_type == StopType.PICKUP else "from"
                submit_to_prefetch(order, computation.key, address_dir)
            else:
                logging.info("No matching computation found for order %s" % order.id)
                ride = create_single_order_ride(order)
                notify_by_email("No matching computation found", "Private ride voucher was sent for order [%s]" % order.id)


@receive_signal(order_status_changed_signal)
def handle_accepted_orders(sender, signal_type, obj, status, **kwargs):
    from ordering.models import ACCEPTED, OrderType
    from ordering.util import create_pickmeapp_ride

    if status == ACCEPTED:
        order = obj
        if order.type == OrderType.PICKMEAPP:
            pickmeapp_ride = create_pickmeapp_ride(order)


#@receive_signal(workstation_offline_signal, workstation_online_signal)
def log_connection_events(sender, signal_type, obj, **kwargs):
    from common.tz_support import utc_now
    from django.core.urlresolvers import reverse
    from google.appengine.api.taskqueue import taskqueue
    from analytics.models import AnalyticsEvent
    from common.util import  log_event, EventType, notify_by_email
    from ordering.signals import   SignalType
    from ordering.station_connection_manager import ALERT_DELTA, handle_dead_workstations

    last_event_qs = AnalyticsEvent.objects.filter(work_station=obj, type__in=[EventType.WORKSTATION_UP, EventType.WORKSTATION_DOWN]).order_by('-create_date')[:1]
    station = obj.station

    if signal_type == SignalType.WORKSTATION_ONLINE:
        if last_event_qs:
            # send workstation reconnect mail
            last_event = last_event_qs[0]
            if last_event.type == EventType.WORKSTATION_DOWN and (utc_now() - last_event.create_date) >= ALERT_DELTA and station.show_on_list:
                msg = u"Workstation is up again:\n\tid = %d station = %s" % (obj.id, obj.dn_station_name)
                notify_by_email(u"Workstation Reconnected", msg=msg)
        elif station.show_on_list:
            # send "new workstation" mail
            msg = u"A new workstation just connected: id = %d station = %s" % (obj.id, obj.dn_station_name)
            notify_by_email(u"New Workstation", msg=msg)

        log_event(EventType.WORKSTATION_UP, station=station, work_station=obj)

    elif signal_type == SignalType.WORKSTATION_OFFLINE:
        log_event(EventType.WORKSTATION_DOWN, station=station, work_station=obj)

        if station.show_on_list:
            # add task to check if workstation is still dead after ALERT_DELTA
            task = taskqueue.Task(url=reverse(handle_dead_workstations),
                                  countdown=ALERT_DELTA.seconds + 1,
                                  params={"workstation_id": obj.id})
            taskqueue.Queue('log-events').add(task)