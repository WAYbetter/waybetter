from django.shortcuts import get_object_or_404, render_to_response
from google.appengine.api.labs import taskqueue
from station_connection_manager import push_order
from django.core.urlresolvers import reverse
from ordering.errors import OrderError, NoWorkStationFoundError
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseNotFound, HttpResponseServerError
from ordering.decorators import passenger_required, internal_task_on_queue
from django.core.serializers import serialize
from django.conf import settings

from models import Order, OrderAssignment, FAILED, ACCEPTED, ORDER_STATUS, IGNORED, ASSIGNED
import dispatcher
import logging
from datetime import datetime

def book_order_async(order):
    logging.info("book_order_async: %d" % order.id)
    task = taskqueue.Task(url=reverse(book_order), params={"order_id": order.id})
    q = taskqueue.Queue('orders')
    q.add(task)

@csrf_exempt
@internal_task_on_queue("orders")
def book_order(request):
    order_id = int(request.POST["order_id"])
    logging.info("book_order_task: %d" % order_id)
    order = get_object_or_404(Order, id=order_id)
    #TODO_WB: check if another dispatching cycle should start
    response = HttpResponse("order handled")
    try:
        order_assignment = dispatcher.assign_order(order)
        enqueue_redispatch_ignored_orders(order_assignment, OrderAssignment.ORDER_ASSIGNMENT_TIMEOUT)
        push_order(order_assignment)
    except NoWorkStationFoundError:
        order.status = FAILED
        order.save()
        logging.warning("no matching workstation found for: %d" % order_id)
        response = HttpResponse("no matching workstation found")
        
        #TODO_WB: send SMS
    except OrderError:
        logging.error("book_order: OrderError: %d" % order_id)
        response = HttpResponseServerError("an error occured while handling order")
        #TODO_WB: send SMS

    return response

def accept_order(order, pickup_time, station):
    order.pickup_time = pickup_time
    order.status = ACCEPTED
    order.station = station
    order.save()

#TODO_WB: send SMS

@passenger_required
def order_status(request, order_id, passenger):
    order = get_object_or_404(Order, id=order_id)
    if order.passenger != passenger:
        return HttpResponseForbidden("You did not order this")

    order_status = ORDER_STATUS
    ordered_on = order.create_date
    status_label = order.status
    polling_interval = settings.POLLING_INTERVAL
    order_assignments = list(OrderAssignment.objects.filter(order=order))
    return render_to_response("order_status.html", locals())

@passenger_required
def get_order_status(request, order_id, passenger):
    order = get_object_or_404(Order, id=order_id)
    if order.passenger != passenger:
        return HttpResponseForbidden("You did not order this")

    order_assignments = OrderAssignment.objects.filter(order=order)

    return HttpResponse(serialize("json", [order] + list(order_assignments), use_natural_keys=True))

@csrf_exempt
@internal_task_on_queue("redispatch-ignored-orders")
def redispatch_ignored_orders(request):
    order_assignment_id = int(request.POST["order_assignment_id"])
    logging.info("redispatch_ignored_orders: %d" % order_assignment_id)
    try:
        order_assignment = OrderAssignment.objects.filter(id=order_assignment_id).get()
    except OrderAssignment.DoesNotExist:
        logging.error("No order assignment found for id: %d" % order_assignment_id)
        return HttpResponse("No order assignment found")

    if order_assignment.status == ASSIGNED:
        if (datetime.now() - order_assignment.create_date).seconds > OrderAssignment.ORDER_ASSIGNMENT_TIMEOUT:
            order_assignment.status = IGNORED
            order_assignment.save()
            book_order_async(order_assignment.order)
        else: # enqueue again to check in 1 sec
            enqueue_redispatch_ignored_orders(order_assignment, 1)

    return HttpResponse("OK")

def enqueue_redispatch_ignored_orders(order_assignment, interval):
    task = taskqueue.Task(url=reverse(redispatch_ignored_orders),
                          countdown=interval,
                          params={"order_assignment_id": order_assignment.id})

    q = taskqueue.Queue('redispatch-ignored-orders')
    q.add(task)
