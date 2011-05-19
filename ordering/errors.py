# Order errors
class OrderError(Exception):
    pass


class UpdateStatusError(OrderError):
    pass


class ShowOrderError(OrderError):
    pass


class UpdateOrderError(OrderError):
    pass


# OrderAssignment errors
class OrderAssignmentError(Exception):
    pass


class NoWorkStationFoundError(OrderError):
    pass


class InvalidRuleSetup(Exception):
    pass