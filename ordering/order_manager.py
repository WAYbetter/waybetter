from google.appengine.api.taskqueue.taskqueue import DuplicateTaskNameError, TaskAlreadyExistsError
from django.shortcuts import get_object_or_404, render_to_response
from google.appengine.api import taskqueue
from google.appengine.api.datastore import RunInTransaction
from station_connection_manager import push_order
from django.core.urlresolvers import reverse
from ordering.errors import OrderError, NoWorkStationFoundError
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseNotFound, HttpResponseServerError
from ordering.decorators import passenger_required, internal_task_on_queue
from django.core.serializers import serialize
from django.conf import settings
from django.utils import translation
from django.utils.translation import ugettext_lazy as _

from models import Order, OrderAssignment, FAILED, ACCEPTED, ORDER_STATUS, IGNORED, ASSIGNED, RATING_CHOICES, ERROR
import dispatcher
import logging
from datetime import datetime
from sharded_counters.models import commit_locked
from ordering.models import Station
from common.sms_notification import send_sms
from common.util import log_event, EventType, translate_to_lang

NO_MATCHING_WORKSTATIONS_FOUND = "no matching workstation found"
ORDER_HANDLED = "order handled"
OK = "OK"

def book_order_async(order, order_assignment=None):
    logging.info("book_order_async: %d" % order.id)
    if order_assignment: # in response to a specific order_assignment we want to ensure only one order is generated
        name = "book-order-%d-%d" % (order.id, order_assignment.id)
        task = taskqueue.Task(url=reverse(book_order), params={"order_id": order.id}, name=name)
    else:
        task = taskqueue.Task(url=reverse(book_order), params={"order_id": order.id})
    
    q = taskqueue.Queue('orders')

    try:
        q.add(task)
    except TaskAlreadyExistsError:
        logging.error("TaskAlreadyExistsError: book order: %d" % order.id)
    except DuplicateTaskNameError:
        logging.error("DuplicateTaskNameError: book order: %d" % order.id)

@csrf_exempt
@internal_task_on_queue("orders")
def book_order(request):
    """
    Book an order: send it to the dispatcher to get an order assignment,
    then pass the assignment to the station manager.
    """
    order_id = int(request.POST["order_id"])
    logging.info("book_order_task: %d" % order_id)
    order = get_object_or_404(Order, id=order_id)

    #TODO_WB: check if another dispatching cycle should start
    response = HttpResponse(ORDER_HANDLED)
    try:
        # choose an assignment for the order and push it to the relevant workstation
        order_assignment = dispatcher.assign_order(order)
        push_order(order_assignment)
        # see what's up with this order in ORDER_ASSIGNMENT_TIMEOUT and dispatch it again if it was ignored
        enqueue_redispatch_ignored_orders(order_assignment, OrderAssignment.ORDER_ASSIGNMENT_TIMEOUT)

    except NoWorkStationFoundError:
        order.status = FAILED
        order.save()
        order.notify()
        log_event(EventType.ORDER_FAILED, order=order, passenger=order.passenger)
        logging.warning("no matching workstation found for: %d" % order_id)
        response = HttpResponse(NO_MATCHING_WORKSTATIONS_FOUND)

        send_sms(order.passenger.international_phone(),
                 _("We're sorry, but we could not find a taxi for you"))
        
    except OrderError:
        order.status = ERROR
        order.save()
        order.notify()
        log_event(EventType.ORDER_ERROR, order=order, passenger=order.passenger)
        logging.error("book_order: OrderError: %d" % order_id)
        response = HttpResponseServerError("an error occured while handling order")
        send_sms(order.passenger.international_phone(),
                 _("We're sorry, but we have encountered an error while handling your request"))

    return response

def accept_order(order, pickup_time, station):
    order.pickup_time = pickup_time
    order.status = ACCEPTED
    order.station = station  
    order.save()

    msg = translate_to_lang("Pickup at %(from)s in %(time)d minutes.\nStation: %(station_name)s, %(station_phone)s", order.language_code) % \
           { "from"             : order.from_raw,
             "time"             : pickup_time,
             "station_name"     : station.name,
             "station_phone"    : station.phones.all()[0].local_phone }

    send_sms(order.passenger.international_phone(), msg)


@passenger_required
def order_status(request, order_id, passenger):
    """View for an order status."""

    order = get_object_or_404(Order, id=order_id)
    if order.passenger != passenger:
        return HttpResponseForbidden("You did not order this")

    order_status = ORDER_STATUS
    ordered_on = order.create_date
    status_label = order.status
    polling_interval = settings.POLLING_INTERVAL
    order_assignments = list(OrderAssignment.objects.filter(order=order))
    rating_choices = RATING_CHOICES
    return render_to_response("order_status.html", locals())


@passenger_required
def get_order_status(request, order_id, passenger):
    #TODO_WB use memchache - saved serialized data
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
        # if time is up mark the assignment as ignored and book the order again.
        if (datetime.now() - order_assignment.create_date).seconds > OrderAssignment.ORDER_ASSIGNMENT_TIMEOUT:
            order_assignment.status = IGNORED
            order_assignment.save()
            log_event(EventType.ORDER_IGNORED,
                      passenger=order_assignment.order.passenger,
                      order=order_assignment.order,
                      order_assignment=order_assignment,
                      station=order_assignment.station,
                      work_station=order_assignment.work_station)

            book_order_async(order_assignment.order, order_assignment)
        else: # enqueue again to check in 1 sec
            enqueue_redispatch_ignored_orders(order_assignment, 1)

    return HttpResponse(OK)

def enqueue_redispatch_ignored_orders(order_assignment, interval):
    task = taskqueue.Task(url=reverse(redispatch_ignored_orders),
                          countdown=interval,
                          params={"order_assignment_id": order_assignment.id})

    q = taskqueue.Queue('redispatch-ignored-orders')
    q.add(task)


@csrf_exempt
@passenger_required
def rate_order(request, order_id, passenger):
    order = get_object_or_404(Order, id=order_id)
    if order.passenger != passenger:
        return HttpResponseForbidden(_("You can't rate this order"))
    rating = int(request.POST["rating"])
    if rating > 0:
        order.passenger_rating = rating
    else:
        order.passenger_rating = None
    order.save()
    log_event(EventType.ORDER_RATED, order=order, rating=rating, passenger=passenger, station=order.station)
    # update async the station rating
    task = taskqueue.Task(url=reverse(update_station_rating),
                          countdown=10,
                          params={"rating": rating, "station_id": order.station_id if order.station else ""})

    q = taskqueue.Queue('update-station-rating')
    q.add(task)
    return HttpResponse("OK")


@csrf_exempt
def update_station_rating(request):
    rating = int(request.POST["rating"])
    station_id = int(request.POST["station_id"]) if request.POST["station_id"] else None 
    if station_id:
        station = get_object_or_404(Station, id=station_id)
        if station.average_rating == 0.0:
            station.number_of_ratings = 1
            station.average_rating = rating
        else:
            sum = station.number_of_ratings * station.average_rating
            sum = sum + rating
            station.number_of_ratings = station.number_of_ratings + 1
            station.average_rating = float(sum) / float(station.number_of_ratings)
        station.save()
    return HttpResponse("OK")

