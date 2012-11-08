from django.utils.translation import ugettext_lazy as _
from common.decorators import receive_signal
from common.signals import AsyncSignal
from common.util import  Enum
from django.utils import simplejson, translation

import logging

class SignalType(Enum):
    RIDE_CREATED               = 1
    RIDE_STATUS_CHANGED        = 2

ride_created_signal                    = AsyncSignal(SignalType.RIDE_CREATED, providing_args=["obj"])
ride_status_changed_signal             = AsyncSignal(SignalType.RIDE_STATUS_CHANGED, providing_args=["obj", "status"])

@receive_signal(ride_created_signal)
def ride_created(sender, signal_type, obj, **kwargs):
    from ordering.models import  PickMeAppRide
    from ordering import dispatcher as pickmeapp_dispatcher

    ride = obj
    logging.info("ride_created_signal: %s" % ride)

    if isinstance(ride, PickMeAppRide):
        pickmeapp_dispatcher.dispatch_ride(ride)

@receive_signal(ride_status_changed_signal)
def log_ride_status_update(sender, signal_type, obj, status, **kwargs):
    from sharing.staff_controller import _log_fleet_update
    ride = obj
    str_status = ride.get_status_display()
    log = "ride %s status changed -> %s" % (ride.id, str_status)
    json = simplejson.dumps({'ride': {'id': ride.id, 'status': str_status}, 'logs': [log]})
    _log_fleet_update(json)


@receive_signal(ride_status_changed_signal)
def handle_failed_ride(sender, signal_type, obj, status, **kwargs):
    from ordering.enums import RideStatus
    from ordering.models import FAILED
    from fleet.fleet_manager import cancel_ride
    from sharing.station_controller import send_ride_in_risk_notification
    from notification.api import notify_passenger

    ride = obj
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
def handle_accepted_ride(sender, signal_type, obj, status, **kwargs):
    from ordering.enums import RideStatus
    from ordering.models import SharedRide
    from sharing.passenger_controller import send_ride_notifications
    from sharing.station_controller import send_ride_voucher
    from google.appengine.ext import deferred
    from fleet import fleet_manager

    ride = obj
    if isinstance(ride, SharedRide) and status == RideStatus.ACCEPTED:
        if ride.dn_fleet_manager_id:
            deferred.defer(fleet_manager.create_ride, ride)
        else:
            logging.info("ride %s has no fleet manager" % ride.id)

        deferred.defer(send_ride_voucher, ride_id=ride.id)

        send_ride_notifications(ride)

@receive_signal(ride_status_changed_signal)
def update_ws(sender, signal_type, obj, status, **kwargs):
    from sharing.station_controller import update_ride
    logging.info("update_ws signal")
    ride = obj
    update_ride(ride)
