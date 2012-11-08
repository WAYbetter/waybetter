import logging
from google.appengine.ext.deferred import deferred
from common.decorators import receive_signal
from common.langsupport.util import translate_to_lang
from common.signals import AsyncSignal
from common.util import  Enum
from django.utils import simplejson
from django.core.urlresolvers import reverse
from django.utils.translation import gettext_noop as _
from fleet.models import FleetManagerRideStatus
from django.conf import settings


class SignalType(Enum):
    TAXIRIDE_POSITION_CHANGED   = 1
    RIDE_STATUS_CHANGED         = 2

positions_update_signal = AsyncSignal(SignalType.TAXIRIDE_POSITION_CHANGED, providing_args=["positions"])
fmr_update_signal = AsyncSignal(SignalType.RIDE_STATUS_CHANGED, providing_args=["fmr"])

@receive_signal(fmr_update_signal)
def log_fmr_update(sender, signal_type, **kwargs):
    import logging
    logging.info("log_fmr_update")
    from sharing.staff_controller import _log_fleet_update
    fmr = kwargs["fmr"]
    json = simplejson.dumps({'fmr': fmr.serialize(), 'logs': [str(fmr)]})
    _log_fleet_update(json)

@receive_signal(fmr_update_signal)
def handle_assign_to_taxi(sender, signal_type, **kwargs):
    from ordering.models import BaseRide, PickMeAppRide
    from sharing.station_controller import update_ride

    fmr = kwargs["fmr"]
    if fmr.status == FleetManagerRideStatus.ASSIGNED_TO_TAXI:

        logging.info("ASSIGNED_TO_TAXI received: notifying passengers: %s" % fmr.id)
        ride = BaseRide.by_uuid(fmr.id)

        if fmr.taxi_id and fmr.taxi_id != ride.taxi_number:
            ride.taxi_number = fmr.taxi_id
            ride.save()

            if isinstance(ride, PickMeAppRide): # PickmeAppRide: send via SMS
                deferred.defer(do_notify_passenger, ride.order, _countdown=40) # wait 40 seconds and then notify passengers

def do_notify_passenger(order):
    from ordering.util import send_msg_to_passenger

    def _notify_order_passenger(order):
        logging.info("Ride status update: notifying passenger about taxi location for order: %s" % order)
        msg = translate_to_lang(_("To view your taxi: "), order.language_code)
        url = " http://%s%s" % (settings.DEFAULT_DOMAIN,
                               reverse("ordering.passenger_controller.track_order", kwargs={"order_id": order.id}))
        msg += url
        send_msg_to_passenger(order.passenger, msg)

    if order:
        ride = order.ride
        if ride:
            for o in ride.orders.all(): _notify_order_passenger(o)
        else:
            _notify_order_passenger(order)


@receive_signal(positions_update_signal)
def log_positions_update(sender, signal_type, positions, **kwargs):
    from sharing.staff_controller import _log_fleet_update
    szd_positions = []
    logs = []
    for p in sorted(positions, key=lambda p: p.timestamp):
        szd_positions.append(p.serialize())
        logs.append(str(p))

    json = simplejson.dumps({'positions': szd_positions, 'logs': logs})
    _log_fleet_update(json)