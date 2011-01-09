class OrderError(Exception):
    pass

class NoWorkStationFoundError(OrderError):
    pass

class InvalidRuleSetup(Exception):
    pass