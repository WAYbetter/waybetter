from common.tz_support import utc_now
from common.util import notify_by_email
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from google.appengine.api.taskqueue import taskqueue
from common.decorators import receive_signal, internal_task_on_queue, catch_view_exceptions
from django.core.urlresolvers import reverse
from ordering import station_connection_manager
from ordering.errors import UpdateStatusError
from ordering.models import WorkStation, PENDING, ASSIGNED, SharedRide, NOT_TAKEN
from datetime import timedelta
import signals
import logging

MSG_DELIVERY_GRACE = 10 # seconds
NOTIFY_STATION_DELTA = timedelta(minutes=10)

def dispatch_ride(ride):
    work_station = assign_ride(ride)
    if work_station:
        station_connection_manager.push_ride(work_station, ride)
        task = taskqueue.Task(url=reverse(push_ride_task), countdown=MSG_DELIVERY_GRACE, params={"ride_id": ride.id, "ws_id": work_station.id})
        taskqueue.Queue('orders').add(task)

    task = taskqueue.Task(url=reverse(mark_ride_not_taken_task), eta=ride.depart_time, params={"ride_id": ride.id})
    q = taskqueue.Queue('orders')
    q.add(task)


def assign_ride(ride):
    work_station = choose_workstation(ride)

    if work_station:
        try:
            ride.station = work_station.station
            ride.change_status(old_status=PENDING, new_status=ASSIGNED) # calls save()
            return work_station

        except UpdateStatusError:
            logging.error("Cannot assign ride: %d" % ride.id)

    return None


def choose_workstation(ride):
    orders = list(ride.orders.all())
    confining_stations = [order.confining_station for order in orders]
    confining_station = confining_stations[0] if all(map(lambda s: s==confining_stations[0], confining_stations)) else None

    log = u"""
ride.id=%s
ride.debug=%s
confining_stations=[%s]

orders:
%s

passengers:
%s
""" % (ride.id, ride.debug, ",".join([unicode(s) for s in confining_stations]),
       "\n".join([unicode(order) for order in orders]), "\n".join([unicode(order.passenger) for order in orders]))

    logging.info(log)

    if confining_station:
        ws_list = WorkStation.objects.filter(station=confining_station, accept_shared_rides=True)
    else:
        ws_list = WorkStation.objects.filter(accept_shared_rides=True)

    if ride.debug:
        ws_list = ws_list.filter(accept_debug=True)

    if ws_list:
        ws = ws_list[0]
        if ws.is_online:
            notify_by_email(u"ride assigned successfully to workstation %s" % ws, msg=log)
        else:
            notify_by_email(u"ride assigned to offline workstation %s" % ws, msg=log)

        return ws

    else:
        logging.error(u"No sharing stations found %s" % log)
        notify_by_email(u"No sharing stations found", msg=log)

        return None


@receive_signal(signals.ride_created_signal)
def ride_created(sender, signal_type, obj, **kwargs):
    logging.info("ride_created_signal: %s" % obj)
    ride = obj
    dispatch_ride(ride)


@csrf_exempt
@catch_view_exceptions
@internal_task_on_queue("orders")
def push_ride_task(request):
    ride_id = request.POST.get("ride_id")
    ws_id = request.POST.get("ws_id")
    try:
        ride = SharedRide.by_id(id=ride_id, safe=False)
        work_station = WorkStation.by_id(ws_id, safe=False)
        if not ride.received_time:
            if utc_now() < ride.depart_time - NOTIFY_STATION_DELTA:
                logging.info("push ride task: ride=%s, workstation=%s" % (ride_id, ws_id))
                station_connection_manager.push_ride(work_station, ride)

                task = taskqueue.Task(url=reverse(push_ride_task), countdown=MSG_DELIVERY_GRACE, params={"ride_id": ride_id, "ws_id": ws_id})
                taskqueue.Queue('orders').add(task)
            else:
                msg = \
"""
depart_time: %s
work station: %s
ride id: %s
""" % (ride.depart_time, work_station, ride_id)
                notify_by_email("Ride not delivered to station", msg=msg)

    except (SharedRide.DoesNotExist, WorkStation.DoesNotExist):
        logging.error("push ride task error: ride=%s, workstation=%s" % (ride_id, ws_id))

    return HttpResponse("OK")


@csrf_exempt
@catch_view_exceptions
@internal_task_on_queue("orders")
def mark_ride_not_taken_task(request):
    ride_id = request.POST.get("ride_id", None)
    try:
        ride = SharedRide.by_id(ride_id, safe=False)
        ride.change_status(new_status=NOT_TAKEN)
        logging.info("Marked ride [%s] as not taken" % ride_id)
        notify_by_email("Ride not taken (not accepted by station)", msg=u"ride=%s\nstation=%s" % (ride.id, ride.station))

    except SharedRide.DoesNotExist:
        logging.error("Error marking ride as not taken: SharedRide.DoesNotExist")
    except UpdateStatusError:
        logging.warning("UpdateStatusError: Error changing ride [%s] status to not taken" % ride_id)

    return HttpResponse("OK")
