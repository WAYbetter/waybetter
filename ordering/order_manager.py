from django.shortcuts import get_object_or_404, render_to_response
from google.appengine.api.labs import taskqueue
from station_connection_manager import push_order
from django.core.urlresolvers import reverse
from ordering.errors import OrderError, NoWorkStationFoundError
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseNotFound, HttpResponseServerError
from ordering.decorators import passenger_required
from django.core.serializers import serialize
from django.conf import settings

import models
import dispatcher
import logging

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
    response = HttpResponse("order handled")
    try:
        order_assignment = dispatcher.assign_order(order)
        push_order(order_assignment)
    except NoWorkStationFoundError:
        order.status = models.FAILED
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
    order.status = models.ACCEPTED
    order.station = station
    order.save()

#TODO_WB: send SMS

@passenger_required
def order_status(request, order_id, passenger):
    order = get_object_or_404(models.Order, id=order_id)
    if order.passenger != passenger:
        return HttpResponseForbidden("You did not order this")

    order_status = models.ORDER_STATUS
    ordered_on = order.create_date
    status_label = order.status
    polling_interval = settings.POLLING_INTERVAL
    order_assignments = list(models.OrderAssignment.objects.filter(order=order))
    return render_to_response("order_status.html", locals())

@passenger_required
def get_order_status(request, order_id, passenger):
    order = get_object_or_404(models.Order, id=order_id)
    if order.passenger != passenger:
        return HttpResponseForbidden("You did not order this")

    order_assignments = models.OrderAssignment.objects.filter(order=order)

    return HttpResponse(serialize("json", [order] + list(order_assignments), use_natural_keys=True))
