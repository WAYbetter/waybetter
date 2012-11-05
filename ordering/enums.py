from common.util import Enum

class RideStatus(Enum):
    ASSIGNED        = 1
    ACCEPTED        = 2
    VIEWED          = 3
    PENDING         = 5
    COMPLETED       = 10
    PROCESSING      = 100