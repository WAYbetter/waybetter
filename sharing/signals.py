from common.signals import AsyncSignal
from common.util import  Enum

class SignalType(Enum):
    RIDE_CREATED               = 1
    RIDE_STATUS_CHANGED        = 2

ride_created_signal                    = AsyncSignal(SignalType.RIDE_CREATED, providing_args=["obj"])
ride_status_changed_signal             = AsyncSignal(SignalType.RIDE_STATUS_CHANGED, providing_args=["obj", "status"])
