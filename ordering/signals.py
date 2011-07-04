from common.signals import AsyncSignal
from common.util import  Enum

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

