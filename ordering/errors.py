class OrderError(Exception):
    pass

class NoWorkStationFoundError(OrderError):
    pass