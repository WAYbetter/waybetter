import logging
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
def notify_passenger(sender, signal_type, **kwargs):
    from ordering.models import Order
    from ordering.util import send_msg_to_passenger

    fmr = kwargs["fmr"]
    order = Order.by_id(fmr.id)

    if fmr.status == FleetManagerRideStatus.ASSIGNED_TO_TAXI and order:

        logging.info("Ride status update: notifying passenger about taxi location for order: %s" % order)
        msg = translate_to_lang(_("To view your taxi: "), order.language_code)
        url = " http://%s%s" % (settings.DEFAULT_DOMAIN,
                               reverse("ordering.passenger_controller.track_order", kwargs={"order_id": order.id}))
        msg += url
        send_msg_to_passenger(order.passenger, msg)

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