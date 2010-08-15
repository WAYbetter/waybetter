from django.shortcuts import get_object_or_404
from google.appengine.api.labs import taskqueue
from station_connection_manager import push_order
import models
import dispatcher
from django.core.urlresolvers import reverse
from ordering.errors import OrderError
from django.views.decorators.csrf import csrf_exempt
import logging
from django.http import HttpResponse

def book_order_async(order):
    logging.info("book_order_async: %d" % order.id)
    task = taskqueue.Task(url=reverse(book_order), params={"order_id": order.id})
    q = taskqueue.Queue('orders')
    q.add(task)
    
@csrf_exempt
def book_order(request):
    order_id = int(request.POST["order_id"])
    logging.info("book_order_task: %d" % order_id)    
    order = get_object_or_404(models.Order, id=order_id)
    #TODO_WB: check if another dispatching cycle should start
    try:
        order_assignment = dispatcher.assign_order(order)
        push_order(order_assignment)
    except OrderError:
        logging.error("book_order: OrderError: %d" % order_id)
        #TODO_WB: send SMS

    return HttpResponse("OK")

def accept_order(order, pickup_time, station):
    order.pickup_time = pickup_time
    order.status = models.ACCEPTED
    order.station = station
    order.save()

    #TODO_WB: send SMS