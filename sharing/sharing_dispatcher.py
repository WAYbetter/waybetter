from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from google.appengine.api.taskqueue import taskqueue
from common.decorators import receive_signal, internal_task_on_queue, catch_view_exceptions
from django.core.urlresolvers import reverse
from ordering import station_connection_manager
from ordering.errors import UpdateStatusError
from ordering.models import WorkStation, PENDING, ASSIGNED, SharedRide, NOT_TAKEN
import signals
import logging

def assign_ride(ride):
    work_station = choose_workstation(ride)

    if work_station:
        try:
            ride.station = work_station.station
            ride.change_status(old_status=PENDING, new_status=ASSIGNED) # calls save()
            return work_station

            signals.ride_status_changed_signal.send(sender='sharing_dispatcher', obj=ride, status=ASSIGNED)

        except UpdateStatusError:
            logging.error("Cannot assign ride: %d" % ride.id)

    return None


def choose_workstation(ride):
    ws_list = WorkStation.objects.filter(accept_shared_rides=True, is_online=True)
    if ws_list:
        return ws_list[0]

    else:
        return None


@receive_signal(signals.ride_created_signal)
def ride_created(sender, signal_type, obj, **kwargs):
    logging.info("ride_created_signal: %s" % obj)
    ride = obj
    work_station = assign_ride(ride)
    if work_station:
        station_connection_manager.push_ride(work_station, ride)
    else:
        logging.error("no work stations for sharing available")

    task = taskqueue.Task(url=reverse(mark_ride_not_taken_task), eta=ride.depart_time, params={"ride_id": ride.id})
    q = taskqueue.Queue('orders')
    q.add(task)


@csrf_exempt
@catch_view_exceptions
@internal_task_on_queue("orders")
def mark_ride_not_taken_task(request):
    ride_id = request.POST.get("ride_id", None)
    try:
        ride = SharedRide.by_id(ride_id)
        ride.change_status(old_status=ASSIGNED, new_status=NOT_TAKEN)
        logging.info("Marked ride [%d] as not taken" % ride.id)
        # TODO_WB: notify by email

    except SharedRide.DoesNotExist:
        logging.error("Error marking ride as not taken: SharedRide.DoesNotExist")
    except UpdateStatusError:
        logging.error("Error changing ride [%d] status to not taken: UpdateStatusError" % ride.id)

    return HttpResponse("OK")
