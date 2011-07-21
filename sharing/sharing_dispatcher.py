from common.decorators import receive_signal
from ordering import station_connection_manager
from ordering.errors import UpdateStatusError
from ordering.models import WorkStation, PENDING, ASSIGNED
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
    ws_list = WorkStation.objects.filter(accept_shared_rides=True, is_online=True) # always return amir_station_1_workstation_1
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

