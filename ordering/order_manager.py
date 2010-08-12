import dispatcher
from ordering.station_connection_manager import push_order
import models

def book_order(order):
   order_assignment = dispatcher.assign_order(order)
   push_order(order_assignment)

def accept_order(order, pickup_time, station):
    order.pickup_time = pickup_time
    order.status = models.ACCEPTED
    order.station = station
    order.save()

    #TODO_WB: send SMS