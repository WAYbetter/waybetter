from django.template.loader import get_template
from google.appengine.api.taskqueue import taskqueue
from google.appengine.api.urlfetch import fetch, POST
from django.views.decorators.csrf import csrf_exempt
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.utils import simplejson
from django.template.context import  Context
from common.decorators import internal_task_on_queue, catch_view_exceptions, receive_signal
from ordering.models import Passenger, Order, SharedRide, RidePoint, StopType, Driver, ACCEPTED
from ordering.util import send_msg_to_passenger, send_msg_to_driver
from sharing.models import RideComputation
from sharing import signals
from datetime import timedelta
import logging
import sharing_dispatcher # so that receive_signal decorator will be evaluted

SHARING_ENGINE_URL = "http://waybetter-route-service2.appspot.com/routeservicega1"
WEB_APP_URL = "http://sharing.latest.waybetter-app.appspot.com/"

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

        computation = RideComputation.objects.get(algo_key=result_id)
        computation.statistics = simplejson.dumps(data["m_OutputStat"])
        computation.completed = True
        computation.save()

        for ride_data in data["m_Rides"]:
            order = Order.by_id(ride_data["m_OrderInfos"].keys()[0])
            ride = SharedRide()
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


@receive_signal(signals.ride_status_changed_signal)
def send_ride_notifications(sender, obj, status, **kwargs):
    if status == ACCEPTED:
        ride = obj

        # notify driver
        task = taskqueue.Task(url=reverse(notify_driver_task),
                              params={"driver_id": ride.driver.id, "msg": get_driver_msg(ride)})
        q = taskqueue.Queue('ride-notifications')
        q.add(task)

        # notify passengers
        pickups = ride.points.filter(type=StopType.PICKUP)
        for p in pickups:
            passengers = [order.passenger for order in p.pickup_orders.all()]
            for passenger in passengers:
                task = taskqueue.Task(url=reverse(notify_passenger_task),
                                      params={"passenger_id": passenger.id, "msg": get_passenger_msg(passenger, ride)})
                q = taskqueue.Queue('ride-notifications')
                q.add(task)


@csrf_exempt
@catch_view_exceptions
@internal_task_on_queue("ride-notifications")
def notify_driver_task(request):
    driver = Driver.by_id(request.POST['driver_id'])
    msg = request.POST.get('msg', None)
    send_msg_to_driver(driver, msg)

    return HttpResponse("OK")


@csrf_exempt
@catch_view_exceptions
@internal_task_on_queue("ride-notifications")
def notify_passenger_task(request):
    passenger = Passenger.by_id(request.POST['passenger_id'])
    msg = request.POST.get('msg', None)
    send_msg_to_passenger(passenger, msg)

    return HttpResponse("OK")

# UTILITY FUNCTIONS

def get_driver_msg(ride):
    t = get_template("driver_notification_msg.template")
    template_data = {'pickups':
                         [{'address': p.address,
                           'time': p.stop_time.strftime("%H:%M"),
                           'num_passengers': p.pickup_orders.count(),
                           'phones': [order.passenger.phone for order in p.pickup_orders.all()]}

                         for p in ride.points.filter(type=StopType.PICKUP).order_by("stop_time")],

                     'dropoffs':
                         [{'address': p.address,
                           'time': p.stop_time.strftime("%H:%M"),
                           'num_passengers': p.dropoff_orders.count(),
                           'phones': [order.passenger.phone for order in p.dropoff_orders.all()]}

                         for p in ride.points.filter(type=StopType.DROPOFF).order_by("stop_time")]
    }
    return t.render(Context(template_data))


def get_passenger_msg(passenger, ride):
    t = get_template("passenger_notification_msg.template")

    orders = [{'pickup_time': o.pickup_point.stop_time.strftime("%H:%M"), 'pickup_address': o.pickup_point.address,
               'dropoff_time': o.dropoff_point.stop_time.strftime("%H:%M"), 'dropoff_address': o.dropoff_point.address}
    for o in Order.objects.filter(passenger=passenger, ride=ride)]

    template_data = {'orders': orders, 'driver': ride.driver}
    return t.render(Context(template_data))