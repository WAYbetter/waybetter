from google.appengine.api.taskqueue import taskqueue
from google.appengine.api.urlfetch import fetch, POST
from billing.enums import BillingStatus
from django.views.decorators.csrf import csrf_exempt
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.utils import simplejson
from common.decorators import internal_task_on_queue, catch_view_exceptions
from ordering.models import  Order, SharedRide, RidePoint, StopType, RideComputation, APPROVED
from sharing import signals
from datetime import timedelta
import urllib
import logging
import settings

TELMAP = 2
WAZE = 3

SHARING_ENGINE_DOMAIN = "http://waybetter-route-service%s.appspot.com" % WAZE
SHARING_ENGINE_URL = "/".join([SHARING_ENGINE_DOMAIN, "routeservicega1"])
PRE_FETCHING_URL = "/".join([SHARING_ENGINE_DOMAIN, "prefetch"])
WEB_APP_URL = "http://dev.latest.waybetter-app.appspot.com/"

def submit_to_prefetch(order, key, address_type):
    address = getattr(order, "%s_raw" % address_type).encode("utf-8")
    payload = urllib.urlencode({'id': key,
                                'name': address,
                                'latitude': getattr(order, "%s_lat" % address_type),
                                'longitude': getattr(order, "%s_lon" % address_type)})

    result = fetch(PRE_FETCHING_URL, payload=payload, method=POST, deadline=10)
    if result.status_code == 200:
        logging.info("submitted to prefetching %s: payload=%s, response=%s" % (address, payload, result.content))
    else:
        logging.error("error while prefetching order %s" % order.id)
    return result


def submit_orders_for_ride_calculation(orders, key=None, params=None):
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

    response = fetch(SHARING_ENGINE_URL, payload="submit=%s" % payload, method=POST, deadline=50)
    data = simplejson.loads(response.content) or {}
    error = data.get("m_Error") if data else "EMPTY RESPONSE"
    if response.status_code != 200 or error:
        logging.error("error submitting orders for ride calculation (status=%s): %s" % (response.status_code, error))
        return None
    else:
        return data.get("m_Key").strip()


@csrf_exempt
@catch_view_exceptions
@internal_task_on_queue("orders")
def submit_computations_task(request):
    key = request.POST.get("computation_key")
    computations = RideComputation.objects.filter(key=key, submitted=False)
    if computations:
        params = {'debug': computations[0].debug}

        approved_orders = []
        orders = [order for c in computations for order in c.orders.all()]
        for order in orders:
            if order.status == APPROVED:
                logging.info("submitting %s" % order)
                approved_orders.append(order)
            else:
                logging.info("NOT submitting %s (status not approved)" % order)

        algo_key = submit_orders_for_ride_calculation(approved_orders, key, params=params)
        logging.info(
            "submitted %s approved orders: computation_key=%s algo_key=%s params=%s." % (len(approved_orders), key, algo_key, params))

        for computation in computations:
            computation.algo_key = algo_key
            computation.submitted = True
            computation.save()

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

        computations = RideComputation.objects.filter(algo_key=result_id)

        debug = bool(data.get("m_Debug"))
        for ride_data in data["m_Rides"]:
            ride = SharedRide()
            ride.debug = debug

            computation = computations[0]
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

        for computation in computations:
            computation.statistics = simplejson.dumps(data.get("m_OutputStat"))
            computation.completed = True
            computation.save()

    return HttpResponse("OK")