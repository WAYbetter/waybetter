from common.decorators import receive_signal
from common.signals import AsyncSignal
from common.util import  Enum
from django.utils import simplejson
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
def notify_passengers(sender, signal_type, obj, status, **kwargs):
    from ordering.enums import RideStatus
    from sharing.passenger_controller import send_ride_notifications

    ride = obj
    if status == RideStatus.ACCEPTED:
        send_ride_notifications(ride)

@receive_signal(ride_status_changed_signal)
def update_ws(sender, signal_type, obj, status, **kwargs):
    from sharing.station_controller import update_ride

    ride = obj
    station = ride.station
    if station:
        for ws in station.work_stations.all(): # maybe send only to online stations?
            update_ride(ws, ride)
    else:
        logging.info("no station on changed ride")