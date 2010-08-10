import dispatcher
from ordering.station_connection_manager import push_order

def book_order(order):
   order_assignment = dispatcher.assign_order(order)
#   push_order(order_assignment)