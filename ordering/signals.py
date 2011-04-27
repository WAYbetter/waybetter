from common.signals import AsyncSignal

book_order_signal                       = AsyncSignal(providing_args=["order"])
order_assigned_signal                   = AsyncSignal(providing_args=["order", "order_assignment"])
order_assignment_status_change_signal   = AsyncSignal(providing_args=["order", "order_assignment", "status"])

