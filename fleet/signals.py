from common.signals import AsyncSignal
from common.util import  Enum

class SignalType(Enum):
    TAXIRIDE_POSITION_CHANGED   = 1
    RIDE_STATUS_CHANGED         = 2

positions_update_signal = AsyncSignal(SignalType.RIDE_STATUS_CHANGED, providing_args=["positions"])
fmr_update_signal = AsyncSignal(SignalType.TAXIRIDE_POSITION_CHANGED, providing_args=["fmr"])
