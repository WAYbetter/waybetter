from common.decorators import receive_signal
from common.signals import AsyncSignal
from common.util import  Enum
from django.utils import simplejson

class SignalType(Enum):
    TAXIRIDE_POSITION_CHANGED   = 1
    RIDE_STATUS_CHANGED         = 2

positions_update_signal = AsyncSignal(SignalType.TAXIRIDE_POSITION_CHANGED, providing_args=["positions"])
fmr_update_signal = AsyncSignal(SignalType.RIDE_STATUS_CHANGED, providing_args=["fmr"])

@receive_signal(fmr_update_signal)
def log_fmr_update(sender, signal_type, fmr, **kwargs):
    import logging
    logging.info("log_fmr_update")
    from sharing.staff_controller import _log_fleet_update
    json = simplejson.dumps({'fmr': fmr.serialize(), 'logs': [str(fmr)]})
    _log_fleet_update(json)

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