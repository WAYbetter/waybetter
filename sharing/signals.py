from common.decorators import receive_signal
from common.signals import AsyncSignal
from common.util import  Enum
from datetime import timedelta
from django.utils import  translation
from django.utils.translation import ugettext_lazy as _
from google.appengine.ext import deferred
import logging

RIDE_TEXT_TIMEOUT = 120

class SignalType(Enum):
    RIDE_CREATED               = 1
    RIDE_STATUS_CHANGED        = 2
    RIDE_UPDATED               = 3
    RIDE_DELETED               = 4

ride_created_signal                    = AsyncSignal(SignalType.RIDE_CREATED, providing_args=["obj"])
ride_deleted_signal                    = AsyncSignal(SignalType.RIDE_DELETED, providing_args=["ride"])
ride_updated_signal                    = AsyncSignal(SignalType.RIDE_UPDATED, providing_args=["obj"])
ride_status_changed_signal             = AsyncSignal(SignalType.RIDE_STATUS_CHANGED, providing_args=["obj", "status"])

@receive_signal(ride_created_signal)
def ride_created(sender, signal_type, obj, **kwargs):
    from ordering.models import  PickMeAppRide
    from ordering import dispatcher as pickmeapp_dispatcher

    ride = obj
    logging.info("ride_created_signal: %s" % ride)

    if isinstance(ride, PickMeAppRide):
        pickmeapp_dispatcher.dispatch_ride(ride)


@receive_signal(ride_deleted_signal)
def handle_deleted_ride(sender, signal_type, ride, **kwargs):
    from sharing.station_controller import update_data

    logging.info("handle_deleted_ride")
    assigned_station = ride.station
    if assigned_station:
        logging.info("updating assigned_station: %s" % assigned_station.id)
        update_data(assigned_station)


@receive_signal(ride_status_changed_signal)
def handle_failed_ride(sender, signal_type, ride, status, **kwargs):
    from ordering.enums import RideStatus
    from ordering.models import FAILED
    from fleet.fleet_manager import cancel_ride
    from sharing.station_controller import send_ride_in_risk_notification
    from notification.api import notify_passenger

    if ride.status == RideStatus.FAILED:
        logging.info("handling FAILED ride: %s" % ride.id)

        current_lang = translation.get_language()
        # cancel ride
        cancel_ride(ride)

        # notify us
        send_ride_in_risk_notification(u"Ride failed because it was not accepted in time", ride.id)

        # cancel orders and notify passengers
        for order in ride.orders.all():
            order.change_status(new_status=FAILED)
            translation.activate(order.language_code)

            notify_passenger(order.passenger, _("We're sorry but we couldn't find a taxi for you this time. (Order: %s)") % order.id)

        translation.activate(current_lang)

@receive_signal(ride_status_changed_signal)
def handle_viewed_ride(sender, signal_type, ride, status, **kwargs):
    from ordering.enums import RideStatus
    from ordering.models import SharedRide
    from fleet import fleet_manager

    if isinstance(ride, SharedRide) and status == RideStatus.VIEWED:
        if ride.dn_fleet_manager_id:
            deferred.defer(fleet_manager.create_ride, ride)
        else:
            logging.info("ride %s has no fleet manager" % ride.id)


@receive_signal(ride_status_changed_signal)
def handle_accepted_ride(sender, signal_type, ride, status, **kwargs):
    from ordering.enums import RideStatus
    from ordering.models import SharedRide
    from sharing.passenger_controller import send_ride_notifications
    from sharing.station_controller import send_ride_voucher
    from fleet.fleet_manager import send_ride_intro_text


    if isinstance(ride, SharedRide) and status == RideStatus.ACCEPTED:
        deferred.defer(send_ride_voucher, ride_id=ride.id)
        send_ride_notifications(ride)

        points = ride.points.all().order_by("stop_time")
        current_point = points[0]
        deferred.defer(ride_text_sentinel, ride=ride, current_point=current_point, _eta=(current_point.stop_time - timedelta(seconds=RIDE_TEXT_TIMEOUT)) )
        send_ride_intro_text(ride)

def ride_text_sentinel(ride, current_point):
    from fleet.fleet_manager import send_ride_point_text

    points = list(ride.points.all().order_by("stop_time"))
    next_point = None
    try: # setup sentinel for next point
        next_point = points[points.index(current_point) +1]
        deferred.defer(ride_text_sentinel, ride=ride, current_point=next_point, _eta=(next_point.stop_time - timedelta(seconds=RIDE_TEXT_TIMEOUT)) )
    except ValueError:
        pass

    if not current_point.dispatched:
        current_point.update(dispatched=True)
        send_ride_point_text(ride, current_point, next_point=next_point)

@receive_signal(ride_updated_signal)
def update_ws(sender, signal_type, ride, **kwargs):
    from sharing.station_controller import update_ride
    logging.info("update_ws signal")
    update_ride(ride)
