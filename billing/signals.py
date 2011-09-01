from common.signals import AsyncSignal
from common.util import  Enum

class BillingSignalType(Enum):
    APPROVED                    = 1
    FAILED                      = 2
    CHARGED                     = 3

billing_approved_signal = AsyncSignal(BillingSignalType.APPROVED, providing_args=["obj"])
billing_failed_signal   = AsyncSignal(BillingSignalType.FAILED, providing_args=["obj"])
billing_charged_signal  = AsyncSignal(BillingSignalType.CHARGED, providing_args=["obj"])



