from common.util import Enum

class BillingStatus(Enum):
    APPROVED	= 0 # J5
    FAILED		= 1
    PENDING		= 2
    PROCESSING	= 3
    CANCELLED	= 4
    CHARGED     = 5 # J4
    