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
NOTIFY_STATION_DELTA = timedelta(minutes=5)

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
    ws_list = WorkStation.objects.filter(accept_shared_rides=True, is_online=True)
    if ride.debug:
        ws_list = ws_list.filter(accept_debug=True)
    if ws_list:
        return ws_list[0]
    else:
        logging.error("no work stations for sharing available (ride.debug=%s)" % ride.debug)
        return None


@receive_signal(signals.ride_created_signal)
def ride_created(sender, signal_type, obj, **kwargs):
    logging.info("ride_created_signal: %s" % obj)
    ride = obj
    work_station = assign_ride(ride)
    if work_station:
        station_connection_manager.push_ride(work_station, ride)
        task = taskqueue.Task(url=reverse(push_ride_task), countdown=MSG_DELIVERY_GRACE, params={"ride_id": ride.id, "ws_id": work_station.id})
        taskqueue.Queue('orders').add(task)

    task = taskqueue.Task(url=reverse(mark_ride_not_taken_task), eta=ride.depart_time, params={"ride_id": ride.id})
    q = taskqueue.Queue('orders')
    q.add(task)


@csrf_exempt
@catch_view_exceptions
@internal_task_on_queue("orders")
def push_ride_task(request):
    ride_id = request.POST.get("ride_id")
    ws_id = request.POST.get("ws_id")
    try:
        ride = SharedRide.by_id(id=ride_id, safe=False)
        if not ride.received_time:
            if utc_now() < ride.depart_time - NOTIFY_STATION_DELTA:
                logging.info("push ride task: ride=%s, workstation=%s" % (ride_id, ws_id))
                work_station = WorkStation.by_id(ws_id, safe=False)
                station_connection_manager.push_ride(work_station, ride)

                task = taskqueue.Task(url=reverse(push_ride_task), countdown=MSG_DELIVERY_GRACE, params={"ride_id": ride_id, "ws_id": ws_id})
                taskqueue.Queue('orders').add(task)
            else:
                msg = \
"""
depart_time: %s
work station: %s
ride id: %s
""" % (ride.depart_time, ws_id, ride_id)
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
        ride.change_status(old_status=ASSIGNED, new_status=NOT_TAKEN)
        logging.info("Marked ride [%d] as not taken" % ride.id)
        # TODO_WB: notify by email

    except SharedRide.DoesNotExist:
        logging.error("Error marking ride as not taken: SharedRide.DoesNotExist")
    except UpdateStatusError:
        logging.warning("Error changing ride [%d] status to not taken: UpdateStatusError" % ride.id)

    return HttpResponse("OK")
