from google.appengine.api.taskqueue import taskqueue
from google.appengine.api.taskqueue.taskqueue import TaskAlreadyExistsError
from google.appengine.api.urlfetch import fetch, POST
from common.tz_support import to_task_name_safe
from django.views.decorators.csrf import csrf_exempt
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.utils import simplejson, translation
from django.utils.translation import ugettext as _
from common.decorators import internal_task_on_queue, catch_view_exceptions, catch_view_exceptions_retry
from common.util import safe_fetch, notify_by_email
from ordering.models import  Order, SharedRide, RidePoint, StopType, RideComputation, APPROVED, RideComputationStatus, FAILED
from ordering.util import send_msg_to_passenger
from sharing import signals
from datetime import timedelta, datetime
import urllib
import logging
import settings
from sharing.errors import BookRideError

TELMAP = 4
WAZE = 3

SHARING_ENGINE_DOMAIN = "http://waybetter-route-service%s.appspot.com" % TELMAP
SHARING_ENGINE_URL = "/".join([SHARING_ENGINE_DOMAIN, "routeservicega1"])
SEC_SHARING_ENGINE_URL = "http://waybetter-route-service-backup.appspot.com/routeservicega1"

PRE_FETCHING_URL = "/".join([SHARING_ENGINE_DOMAIN, "prefetch"])
WEB_APP_URL = "http://dev.latest.waybetter-app.appspot.com/"


COMPUTATION_FIRST_SUBMIT = 1
COMPUTATION_SUBMIT_TO_SECONDARY = 2
COMPUTATION_ABORT = 3

COMPUTATION_SUBMIT_TO_SECONDARY_TIMEOUT = 5 # minutes
COMPUTATION_ABORT_TIMEOUT = 5 # minutes

def submit_to_prefetch(order, key, address_type):
    address = getattr(order, "%s_raw" % address_type).encode("utf-8")
    payload = urllib.urlencode({'id': key,
                                'name': address,
                                'latitude': getattr(order, "%s_lat" % address_type),
                                'longitude': getattr(order, "%s_lon" % address_type)})


    task = taskqueue.Task(url=reverse(submit_to_prefetch_task), params={"address": address, "payload": payload})
    try:
        taskqueue.Queue('orders').add(task)
    except Exception, e:
        logging.error(e)


@csrf_exempt
@catch_view_exceptions
@internal_task_on_queue("orders")
def submit_to_prefetch_task(request):
    address = request.POST.get("address")
    payload = request.POST.get("payload")

    result = safe_fetch(PRE_FETCHING_URL, payload=payload, method=POST, deadline=50)
    if result:
        logging.info("submitted to prefetching %s: payload=%s, response=%s" % (address, payload, result.content))
    else:
        logging.error("error while prefetching order. payload = %s" % payload)

    return HttpResponse("OK")

def submit_orders_for_ride_calculation(orders, key=None, params=None, use_secondary=False):
    """
    Submit orders to sharing algorithm
    @param orders: a list of orders to submit
    @param key: prefetching key
    @param params: additional parameters
    @return: the sharing algorithm key for the computation if submit was successful, None otherwise
    """
    callback = ride_calculation_complete_noop if settings.DEV else ride_calculation_complete
    payload = {
        "orders": [o.serialize_for_sharing() for o in orders],
        "callback_url": reverse(callback, prefix=WEB_APP_URL),
        "hotspot_id": key,
        "parameters": params
    }

    payload = simplejson.dumps(payload)
    logging.info("payload = %s" % payload)

    server = SEC_SHARING_ENGINE_URL if use_secondary else SHARING_ENGINE_URL

    response = fetch(server, payload="submit=%s" % payload, method=POST, deadline=50)
    data = simplejson.loads(response.content) or {}
    error = data.get("m_Error") if data else "EMPTY RESPONSE"
    if response.status_code != 200 or error:
        logging.error("error submitting orders for ride calculation (status=%s): %s" % (response.status_code, error))
        return None
    else:
        return data.get("m_Key").strip()

def submit_computations(computation_key, submit_time, submit_step=COMPUTATION_FIRST_SUBMIT):
    """
    Submit the computation to the algo engine

    @param computation_key: the key denoting the computation
    @param submit_time: eta for the task
    """

    task_name = "key_%s_submit_on_%s" % (computation_key, to_task_name_safe(submit_time))
    task = taskqueue.Task(url=reverse(submit_computations_task), params={'computation_key': computation_key, 'submit_step': submit_step},
                                          eta=submit_time,
                                          name=task_name)
    try:
        taskqueue.Queue('orders').add(task)
        logging.info("submit computation [key=%s]: on %s" % (computation_key, submit_time))
    except TaskAlreadyExistsError:
        logging.info("computation [key=%s] already scheduled for %s" % (computation_key, submit_time))
    except Exception, e:
        logging.error(e)
        raise BookRideError(e)


def notify_aborted_computation(orders, computation):
    current_lang = translation.get_language()
    for order in orders:
        translation.activate(order.language_code)
        msg = _("We are sorry, but order #%s could not be completed") % order.id
        send_msg_to_passenger(order.passenger, msg)

    translation.activate(current_lang)

    email_body = "The following computation was aborted because it did not complete after at least %d minutes:\n%s" % (COMPUTATION_ABORT_TIMEOUT + COMPUTATION_SUBMIT_TO_SECONDARY_TIMEOUT, str(computation))

    notify_by_email("Computations Aborted", email_body)


def abort_computation(computation):
    orders = []
    computation.change_status(new_status=RideComputationStatus.ABORTED)
    for order in computation.orders.all():
        order.change_status(new_status=FAILED)
        orders.append(order)

    orders = set(orders)
    notify_aborted_computation(orders, computation)

@csrf_exempt
@catch_view_exceptions_retry
@internal_task_on_queue("orders")
def submit_computations_task(request):
    key = request.POST.get("computation_key")
    submit_step = int(request.POST.get("submit_step"))
    logging.info("submit_computations_task: submit_step=%d" % submit_step)
    computation = None

    # first lets get rid of the duplicate ride_computations we might have
    if submit_step == COMPUTATION_FIRST_SUBMIT:
        computation = RideComputation.objects.filter(key=key, status=RideComputationStatus.PENDING).order_by("create_date")[0]
        if computation.change_status(old_status=RideComputationStatus.PENDING, new_status=RideComputationStatus.PROCESSING):
            computations = RideComputation.objects.filter(key=key, status=RideComputationStatus.PENDING)
            orders = [order for c in computations for order in c.orders.all()]
            for o in orders:
                o.computation = computation
                o.save()
            for c in computations: # delete old, emptied computations
                c.delete()
        else: # abort
            return HttpResponse("ABORTED")

        if not computation: # maybe an exception interrupted the first run
            try:
                computation = RideComputation.objects.get(key=key, status=RideComputationStatus.PROCESSING)
            except RideComputation.DoesNotExist:
                pass


    else:
        try:
            computation = RideComputation.objects.get(key=key, status=RideComputationStatus.SUBMITTED)
        except RideComputation.DoesNotExist:
            pass
        
    if computation:
        if submit_step == COMPUTATION_ABORT: # this is the second verification cycle
            abort_computation(computation)
            return HttpResponse("ABORTED") # abort task

        params = {'debug': computation.debug}

        approved_orders = list(computation.orders.filter(status=APPROVED))

        if not approved_orders:
            computation.change_status(old_status=RideComputationStatus.PROCESSING, new_status=RideComputationStatus.SUBMITTED) # saves
            return HttpResponse("NO APPROVED ORDERS")

        algo_key = submit_orders_for_ride_calculation(approved_orders, key, params=params, use_secondary=bool(submit_step==COMPUTATION_SUBMIT_TO_SECONDARY))
        computation.algo_key = algo_key
        computation.change_status(old_status=RideComputationStatus.PROCESSING, new_status=RideComputationStatus.SUBMITTED) # saves
        
        if submit_step == COMPUTATION_FIRST_SUBMIT:
            submit_computations(key, datetime.now() + timedelta(minutes=COMPUTATION_SUBMIT_TO_SECONDARY_TIMEOUT), submit_step=COMPUTATION_SUBMIT_TO_SECONDARY)
        elif submit_step == COMPUTATION_SUBMIT_TO_SECONDARY:
            submit_computations(key, datetime.now() + timedelta(minutes=COMPUTATION_ABORT_TIMEOUT), submit_step=COMPUTATION_ABORT)

        logging.info(
            "submitted %s approved orders: computation_key=%s algo_key=%s params=%s." % (len(approved_orders), key, algo_key, params))


    else:
        logging.info("no un-submitted computations for key=%s" % key)

    return HttpResponse("OK")


@csrf_exempt
def ride_calculation_complete_noop(request):
    """
    Callback for requests by dev server: do nothing.
    """
    logging.info("ride_calculation_complete NOOP: %s" % request)
    return HttpResponse("OK")


@csrf_exempt
def ride_calculation_complete(request):
    logging.info("ride_calculation_complete: %s" % request)
    result_id = request.POST.get('id')
    if result_id:
        task = taskqueue.Task(url=reverse(fetch_ride_results_task), params={"result_id": result_id})
        q = taskqueue.Queue('orders')
        q.add(task)

    return HttpResponse("OK")


@csrf_exempt
@catch_view_exceptions
@internal_task_on_queue("orders")
def fetch_ride_results_task(request):
    result_id = request.POST["result_id"]
    result = fetch(SHARING_ENGINE_URL, payload="get=%s" % result_id, method=POST, deadline=30)
    content = result.content.strip()
    if result.status_code == 200 and content:
        data = simplejson.loads(content.decode("utf-8"))
        logging.info("data = %s" % data)

        computation = RideComputation.objects.get(algo_key=result_id)

        debug = bool(data.get("m_Debug"))
        for ride_data in data["m_Rides"]:
            ride = SharedRide()
            ride.debug = debug

            ride.computation = computation
            if computation.hotspot_depart_time:
                ride.depart_time = computation.hotspot_depart_time
                ride.arrive_time = ride.depart_time + timedelta(seconds=ride_data["m_Duration"])
            elif computation.hotspot_arrive_time:
                ride.arrive_time = computation.hotspot_arrive_time
                ride.depart_time = ride.arrive_time - timedelta(seconds=ride_data["m_Duration"])
            ride.save()

            for point_data in ride_data["m_RidePoints"]:
                point = RidePoint()
                point.type = StopType.PICKUP if point_data["m_Type"] == "ePickup" else StopType.DROPOFF
                point.lon = point_data["m_PointAddress"]["m_Longitude"]
                point.lat = point_data["m_PointAddress"]["m_Latitude"]
                point.address = point_data["m_PointAddress"]["m_Name"]
                point.stop_time = ride.depart_time + timedelta(seconds=point_data["m_offset_time"])
                point.ride = ride
                point.save()

                for order_id in point_data["m_OrderIDs"]:
                    order = Order.by_id(int(order_id))
                    order.ride = ride
                    if point.type == StopType.PICKUP:
                        order.pickup_point = point
                    else:
                        order.dropoff_point = point
                    order.save()

            signals.ride_created_signal.send(sender='fetch_ride_results', obj=ride)


        computation.statistics = simplejson.dumps(data.get("m_OutputStat"))
        computation.change_status(new_status=RideComputationStatus.COMPLETED) # saves

    return HttpResponse("OK")