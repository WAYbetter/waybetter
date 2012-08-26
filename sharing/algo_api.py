import traceback
from google.appengine.api.taskqueue import taskqueue
from google.appengine.api.urlfetch import  POST
from google.appengine.ext.deferred import deferred
from common.tz_support import to_task_name_safe
from django.views.decorators.csrf import csrf_exempt
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.utils import simplejson
from common.decorators import internal_task_on_queue, catch_view_exceptions, catch_view_exceptions_retry
from common.util import safe_fetch, notify_by_email, get_uuid, safe_json_loads, Enum
from ordering.models import  Order, SharedRide, RidePoint, StopType, RideComputation, APPROVED, RideComputationStatus, IGNORED, CANCELLED, SHARING_TIME_MINUTES, SHARING_DISTANCE_METERS
from ordering.util import create_single_order_ride
from sharing import signals
from datetime import timedelta, datetime
import urllib
import logging
from django.conf import settings

DEBUG = 1
WAZE = 3
GOOGLE = 4

M2M_ENGINE_DOMAIN = "http://waybetter-route-service3.appspot.com/m2malgo"

SHARING_ENGINE_DOMAIN = "http://waybetter-route-service%s.appspot.com" % GOOGLE
SEC_SHARING_ENGINE_DOMAIN = "http://waybetter-route-service-backup.appspot.com"

SHARING_ENGINE_URL = "/".join([SHARING_ENGINE_DOMAIN, "routeservicega1"])
SEC_SHARING_ENGINE_URL = "/".join([SEC_SHARING_ENGINE_DOMAIN, "routeservicega1"])
PRE_FETCHING_URL = "/".join([SHARING_ENGINE_DOMAIN, "prefetch"])
ROUTING_URL = "/".join([SHARING_ENGINE_DOMAIN, "routes"])

COMPUTATION_FIRST_SUBMIT = 1
COMPUTATION_SUBMIT_TO_SECONDARY = 2
COMPUTATION_ABORT = 3

COMPUTATION_SUBMIT_TO_SECONDARY_TIMEOUT = 3 # minutes
COMPUTATION_ABORT_TIMEOUT = 3 # minutes

class AlgoField(Enum):
    DEBUG = "m_Debug"
    DISTANCE = "m_Distance"
    DROPOFF = "eDropoff"
    DURATION = "m_Duration"
    LAT = "m_Latitude"
    LNG = "m_Longitude"
    NAME = "m_Name"
    OFFSET_TIME = "m_offset_time"
    ORDER_IDS = "m_OrderIDs"
    ORDER_INFOS = "m_OrderInfos"
    OUTPUT_STAT = "m_OutputStat"
    PICKUP = "ePickup"
    POINT_ADDRESS = "m_PointAddress"
    PRICE_SHARING = "m_PriceSharing"
    RIDES = "m_Rides"
    RIDE_ID = "m_RideID"
    RIDE_POINTS = "m_RidePoints"
    TIME_SECONDS = "m_TimeSeconds"
    TYPE = "m_Type"


def find_matches(candidate_rides, order_settings):
    #TODO_WB: do actual call

    payload = {
        AlgoField.RIDES : [r.serialize_for_algo() for r in candidate_rides],
        "order"         : order_settings.serialize(),
        "parameters"    : {
            "debug"                     : order_settings.debug,
            'toleration_factor_minutes' : SHARING_TIME_MINUTES,
            'toleration_factor_meters'  : SHARING_DISTANCE_METERS
        }
    }

    payload = simplejson.dumps(payload)
    logging.info("payload=%s" % payload)
    dt = datetime.now()
    response = safe_fetch(M2M_ENGINE_DOMAIN, payload="submit=%s" % payload, method=POST, deadline=50)
    logging.info("response=%s (took %s seconds)" % (response.content, (datetime.now() - dt).seconds))
    return response


def calculate_route(start_lat, start_lon, end_lat, end_lon):
    payload = urllib.urlencode({
        "start_latitude": start_lat,
        "start_longitude": start_lon,
        "end_latitude": end_lat,
        "end_longitude": end_lon
    })

    url = "%s?%s" % (ROUTING_URL, payload)
    logging.info("algo route: %s" % url)

    response = safe_fetch(url, deadline=15, notify=False)
    content = response.content.strip() if response else None

    result = {
        "estimated_distance": 0.0,
        "estimated_duration": 0.0
    }

    if content:
        route = simplejson.loads(content)
        if "Error" in route:
            logging.error(route["Error"])
        else:
            result = {
                "estimated_distance": float(route[AlgoField.DISTANCE]),
                "estimated_duration": float(route[AlgoField.TIME_SECONDS])
            }

    return result


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
    callback = ride_calculation_complete_noop if settings.LOCAL else ride_calculation_complete
    payload = {
        "orders": [o.serialize_for_sharing() for o in orders],
        "callback_url": reverse(callback, prefix=settings.WEB_APP_URL),
        "hotspot_id": key,
        "parameters": params
    }

    payload = simplejson.dumps(payload)
    logging.info("payload = %s" % payload)

    server = SEC_SHARING_ENGINE_URL if use_secondary else SHARING_ENGINE_URL

    key = None
    response = safe_fetch(server, payload="submit=%s" % payload, method=POST, deadline=50)
    if response:
        data = simplejson.loads(response.content)
        error = data.get("m_Error")
        raw_key = data.get("m_Key")
        if error:
            notify_by_email(u"Error submitting orders to algorithm", u"error was: %s\npayload: %s" % (error, payload))
        elif raw_key:
            key = raw_key.strip()

    return key

def submit_computations(computation_key, submit_time, submit_step=COMPUTATION_FIRST_SUBMIT, computation_id=None):
    """
    Submit the computation to the algo engine

    @param computation_key: the key denoting the computation
    @param submit_time: eta for the task
    """

    task_name = "key_%s_submit_on_%s_%s" % (computation_key, to_task_name_safe(submit_time), get_uuid())
    task = taskqueue.Task(url=reverse(submit_computations_task), eta=submit_time, name=task_name,
                          params={'computation_key': computation_key,
                                  'computation_id': computation_id,
                                  'submit_step': submit_step})
    try:
        taskqueue.Queue('orders').add(task)
        logging.info("submit computation [key=%s]: on %s" % (computation_key, submit_time))
    except Exception, e:
        trc = traceback.format_exc()
        logging.error(trc)
        notify_by_email("Important! submit computations task failed", msg="task_name=%s\n%s" % (task_name, trc))


def notify_aborted_computation(orders, computation):
    email_body = u"The following computation was aborted because it did not complete after at least %(minutes)d minutes:\n%(computation)s" % \
    {"minutes": COMPUTATION_ABORT_TIMEOUT + COMPUTATION_SUBMIT_TO_SECONDARY_TIMEOUT,
     "computation": str(computation)}
    email_body += u"\nA voucher was created for the following orders and sent to station as single order ride:%s" % "\n".join([unicode(o) for o in orders])
    notify_by_email("Computation Aborted", email_body)


def abort_computation(computation):
    orders = computation.orders.all()
    for order in orders:
        ride = create_single_order_ride(order)
        ride.computation = computation
        ride.save()

    computation.change_status(new_status=RideComputationStatus.ABORTED)
    notify_aborted_computation(orders, computation)

@csrf_exempt
@catch_view_exceptions_retry
@internal_task_on_queue("orders")
def submit_computations_task(request):
    key = request.POST.get("computation_key")
    cid = request.POST.get("computation_id") # used in second and third steps for identifying the computation to process
    submit_step = int(request.POST.get("submit_step"))
    logging.info("submit_computations_task: submit_step=%d" % submit_step)
    computation = None

    if submit_step == COMPUTATION_FIRST_SUBMIT:
        pending_computations = RideComputation.objects.filter(key=key, status=RideComputationStatus.PENDING)
        pending_computations = sorted(pending_computations, key = lambda c: c.create_date, reverse=True)
        if pending_computations:
            computation = pending_computations[0]
        else:
            logging.info("skipping: no pending computations with key %s" % key)
            return HttpResponse("OK") # nothing to do, no pending computations
        
        # first lets get rid of the duplicate ride_computations we might have
        if computation.change_status(old_status=RideComputationStatus.PENDING, new_status=RideComputationStatus.PROCESSING):
            computations = RideComputation.objects.filter(key=key, status=RideComputationStatus.PENDING) # TODO_WB: fix for HRD
            orders = [order for c in computations for order in c.orders.all()]
            for o in orders:
                o.computation = computation
                o.save()
            for c in computations: # delete old, emptied computations
                c.delete()
        else: # aborting  - another process changed the same computation. This is OK.
            logging.info("aborting: changing status PENDING->PROCESSING failed")
            return HttpResponse("ABORTED")

        if not computation: # maybe an exception interrupted the first try after status was changed to PROCESSING
            try:
                computation = RideComputation.objects.get(key=key, status=RideComputationStatus.PROCESSING)
            except RideComputation.DoesNotExist:
                pass

    else: # second or third step - get the computation we are responsible for
        computation = RideComputation.by_id(cid)

    if computation:
        # if computation is in final state do nothing
        if computation.status in [RideComputationStatus.ABORTED, RideComputationStatus.IGNORED, RideComputationStatus.COMPLETED]:
            logging.info("nothing to do")
            return HttpResponse("Done")

        elif submit_step == COMPUTATION_ABORT:
            abort_computation(computation)
            return HttpResponse("ABORTED") # abort task

        # first or seconds steps - submit to algo
        params = {'debug': computation.debug,
#                  'toleration_factor': SHARING_TIME_FACTOR,
                  'toleration_factor_minutes': SHARING_TIME_MINUTES,
                  'toleration_factor_meters': SHARING_DISTANCE_METERS
                  }

        approved_orders = []
        for order in computation.orders.all():
            if order.status == APPROVED:
                approved_orders.append(order)
                logging.info("order [%s] APPROVED" % order.id)
            elif order.status == CANCELLED:
                logging.info("skipping: order [%s] CANCELLED" % order.id)
            else:
                order.change_status(new_status=IGNORED)
                logging.info("changed status: order [%s] IGNORED" % order.id)

        if not approved_orders:
            computation.change_status(old_status=RideComputationStatus.PROCESSING, new_status=RideComputationStatus.IGNORED) # saves
            logging.info("ignoring: no approved orders")
            return HttpResponse("NO APPROVED ORDERS")

        algo_key = submit_orders_for_ride_calculation(approved_orders, key, params=params, use_secondary=bool(submit_step==COMPUTATION_SUBMIT_TO_SECONDARY))
        logging.info("got algo key=%s" % algo_key)
        computation.algo_key = algo_key

        # old status can be SUMBITTED or PROCESSING
        computation.change_status(new_status=RideComputationStatus.SUBMITTED) # saves

        if submit_step == COMPUTATION_FIRST_SUBMIT:
            submit_computations(key, datetime.now() + timedelta(minutes=COMPUTATION_SUBMIT_TO_SECONDARY_TIMEOUT), submit_step=COMPUTATION_SUBMIT_TO_SECONDARY, computation_id=computation.id)
        elif submit_step == COMPUTATION_SUBMIT_TO_SECONDARY:
            submit_computations(key, datetime.now() + timedelta(minutes=COMPUTATION_ABORT_TIMEOUT), submit_step=COMPUTATION_ABORT, computation_id=cid)

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
    data = safe_json_loads(request.POST.get('data'))
    # submit_computations_task may take some time to save the algo key and SUMBITTED status
    # so we set a countdown timer in case the algo. called calculation_complete too early
    deferred.defer(handle_calculation_result, result_id, data, _countdown=10)

    return HttpResponse("OK")

def handle_calculation_result(result_id, data):
    """
    @param result_id: the algo-key returned when the orders where submitted
    @param data: the computed ride data
    """

    try:
        computation = RideComputation.objects.get(algo_key=result_id, status=RideComputationStatus.SUBMITTED)
    except RideComputation.DoesNotExist:
        logging.info("can not find computation with status SUBMITTED and algo_key:%s" % result_id)
        return

    if not data:
        logging.error("aborting computation [%s]: no ride data received" % computation.id)
        abort_computation(computation)
        return

    logging.info("data = %s" % data)

    debug = bool(data.get(AlgoField.DEBUG))
    for ride_data in data[AlgoField.RIDES]:
        ride = SharedRide()
        ride.debug = debug
        ride.computation = computation

        first_point = ride_data[AlgoField.RIDE_POINTS][0]
        first_order_id = int(first_point[AlgoField.ORDER_IDS][0])
        first_order = Order.by_id(first_order_id)
        ride.depart_time = first_order.depart_time
        ride.arrive_time = ride.depart_time + timedelta(seconds=ride_data[AlgoField.DURATION])

        ride.save()

        for point_data in ride_data[AlgoField.RIDE_POINTS]:
            point = RidePoint()
            point.type = StopType.PICKUP if point_data[AlgoField.TYPE] == AlgoField.PICKUP else StopType.DROPOFF
            point.lon = point_data[AlgoField.POINT_ADDRESS][AlgoField.LNG]
            point.lat = point_data[AlgoField.POINT_ADDRESS][AlgoField.LAT]
            point.address = point_data[AlgoField.POINT_ADDRESS][AlgoField.NAME]
            point.stop_time = ride.depart_time + timedelta(seconds=point_data[AlgoField.OFFSET_TIME])
            point.ride = ride
            point.save()

            for order_id in point_data[AlgoField.ORDER_IDS]:
                order = Order.by_id(int(order_id))
                order.ride = ride
                if point.type == StopType.PICKUP:
                    order.pickup_point = point
                else:
                    order.dropoff_point = point
                order.save()

        signals.ride_created_signal.send(sender='fetch_ride_results', obj=ride)

    computation.statistics = simplejson.dumps(data.get(AlgoField.OUTPUT_STAT))
    computation.change_status(new_status=RideComputationStatus.COMPLETED) # saves
