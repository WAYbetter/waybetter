from common.decorators import receive_signal
from common.signals import AsyncSignal
from common.util import  Enum, notify_by_email
from django.utils.translation import ugettext as _
import logging

class SignalType(Enum):
    ORDER_CREATED               = 1
    ORDER_STATUS_CHANGED        = 2
    ASSIGNMENT_CREATED          = 3
    ASSIGNMENT_STATUS_CHANGED   = 4
    WORKSTATION_ONLINE          = 5
    WORKSTATION_OFFLINE         = 6

    ORDER_PRICE_CHANGED         = 7

order_created_signal                    = AsyncSignal(SignalType.ORDER_CREATED, providing_args=["obj"])
orderassignment_created_signal          = AsyncSignal(SignalType.ASSIGNMENT_CREATED, providing_args=["obj"])
orderassignment_status_changed_signal   = AsyncSignal(SignalType.ASSIGNMENT_STATUS_CHANGED, providing_args=["obj", "status"])
order_status_changed_signal             = AsyncSignal(SignalType.ORDER_STATUS_CHANGED, providing_args=["order", "status"])
order_price_changed_signal              = AsyncSignal(SignalType.ORDER_PRICE_CHANGED, providing_args=["order", "joined_passenger", "old_price", "new_price"])

workstation_online_signal               = AsyncSignal(SignalType.WORKSTATION_ONLINE, providing_args=["obj"])
workstation_offline_signal              = AsyncSignal(SignalType.WORKSTATION_OFFLINE, providing_args=["obj"])

@receive_signal(order_status_changed_signal)
def handle_approved_orders(sender, signal_type, order, status, **kwargs):
    from common.util import notify_by_email, send_mail_as_noreply
    from common.langsupport.util import translate_to_lang
    from ordering.models import APPROVED
    from sharing.passenger_controller import get_passenger_ride_email

    logging.info("handle_approved_orders: %s" % status)
    if status == APPROVED:

        # send confirmation email
        passenger = order.passenger
        if passenger.user and passenger.user.email:
            msg = get_passenger_ride_email(order)
            send_mail_as_noreply(passenger.user.email, translate_to_lang("WAYbetter Order Confirmation", order.language_code), html=msg)
            notify_by_email("Order Confirmation [%s]%s" % (order.id, " (DEBUG)" if order.debug else ""), html=msg)


@receive_signal(order_status_changed_signal)
def handle_accepted_orders(sender, signal_type, order, status, **kwargs):
    from ordering.models import ACCEPTED, OrderType
    from ordering.util import create_pickmeapp_ride

    if status == ACCEPTED:
        if order.type == OrderType.PICKMEAPP:
            pickmeapp_ride = create_pickmeapp_ride(order)


@receive_signal(order_status_changed_signal)
def handle_cancelled_orders(sender, signal_type, order, status, **kwargs):
    from ordering.models import CANCELLED, PromoCodeActivation
    from ordering.ordering_controller import update_ride_remove_order

    if status == CANCELLED:
        notify_by_email("Order Confirmation [%s]%s" % (order.id, " (DEBUG)" if order.debug else ""), msg="CANCELLED")
        update_ride_remove_order(order)
        if order.promo_code:
            promo_activation = PromoCodeActivation.objects.get(passenger=order.passenger, promo_code=order.promo_code)
            promo_activation.forfeit()


@receive_signal(order_price_changed_signal)
def handle_price_updates(sender, signal_type, order, joined_passenger, old_price, new_price, **kwargs):
    from notification.api import notify_passenger

    logging.info("order [%s] price changed: %s -> %s" % (order.id, old_price, new_price))
    if old_price and new_price:
        savings = "%g" % (old_price - new_price)
        if savings > 0:
            notify_passenger(order.passenger, _(u"%(name)s joined your taxi - you save %(savings)s NIS!") % {"name": joined_passenger.name, "savings": savings})

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