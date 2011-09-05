from google.appengine.api.taskqueue import taskqueue
from google.appengine.api.urlfetch import fetch, POST
from django.views.decorators.csrf import csrf_exempt
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.utils import simplejson
from common.decorators import internal_task_on_queue, catch_view_exceptions
from ordering.models import  Order, SharedRide, RidePoint, StopType, RideComputation
from sharing import signals
from datetime import timedelta
import urllib
import logging
import settings

SHARING_ENGINE_DOMAIN = "http://waybetter-route-service2.appspot.com"
SHARING_ENGINE_URL = "/".join([SHARING_ENGINE_DOMAIN, "routeservicega1"])
PRE_FETCHING_URL = "/".join([SHARING_ENGINE_DOMAIN, "prefetch"])
WEB_APP_URL = "http://sharing.latest.waybetter-app.appspot.com/"

def submit_to_prefetch(order, key, address_type):
    payload = urllib.urlencode({'id': key,
                                'name': getattr(order, "%s_raw" % address_type).encode("utf-8"),
                                'latitude': getattr(order, "%s_lat" % address_type),
                                'longitude': getattr(order, "%s_lon" % address_type)})

    result = fetch(PRE_FETCHING_URL, payload=payload, method=POST, deadline=10)
    if result.status_code == 200:
        logging.info("submitted to prefetching order %s: payload=%s, response=%s" % (order.id, payload, result.content))
    else:
        logging.error("error while prefetching order %s" % order.id)
    return result


def submit_orders_for_ride_calculation(orders, key=None, params=None):
    callback = ride_calculation_complete_noop if settings.is_dev() else ride_calculation_complete
    payload = {
        "orders": [o.serialize_for_sharing() for o in orders],
        "callback_url": reverse(callback, prefix=WEB_APP_URL),
        "hotspot_id": key,
        "parameters": params
    }

    payload = simplejson.dumps(payload)
    logging.info("payload = %s" % payload)

    response = fetch(SHARING_ENGINE_URL, payload="submit=%s" % payload, method=POST, deadline=50)
    if response.status_code != 200 or not response.content:
        logging.error("error submitting orders for ride calculation: response=%s" % response.content)

    return response


@csrf_exempt
@catch_view_exceptions
@internal_task_on_queue("orders")
def submit_computation_task(request):
    computation = RideComputation.by_id(request.POST.get("computation_id"))
    if computation:
        response = submit_orders_for_ride_calculation(computation.orders.all(), computation.key)
        if response.content:
            computation.algo_key = response.content.strip()
            computation.save()
    else:
        logging.error("error submitting computation for calculation: %s" % request.POST.get("computation_id"))

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

        try:
            computation = RideComputation.objects.get(algo_key=result_id)
            computation.statistics = simplejson.dumps(data.get("m_OutputStat"))
            computation.completed = True
            computation.save()
        except RideComputation.DoesNotExist:
            logging.error("computation does not exist. this usually happens when fetching algo. results submitted by localhost or vice versa")

        debug = bool(data.get("m_Debug"))
        for ride_data in data["m_Rides"]:
            ride = SharedRide()
            ride.debug = debug
            order = Order.by_id(ride_data["m_OrderInfos"].keys()[0])
            if order.depart_time:
                ride.depart_time = order.depart_time
                ride.arrive_time = ride.depart_time + timedelta(seconds=ride_data["m_Duration"])
            else:
                ride.arrive_time = order.arrive_time
                ride.depart_time = ride.arrive_time - timedelta(seconds=ride_data["m_Duration"])

            #            hack for testing
            #            ride.depart_time = datetime.now() + timedelta(minutes=3)
            #            ride.arrive_time = ride.depart_time + timedelta(seconds=ride_data["m_Duration"])

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

    return HttpResponse("OK")