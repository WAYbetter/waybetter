from ordering.errors import UpdateStatusError
from ordering.models import WorkStation, PENDING, ASSIGNED
import logging

def assign_ride(ride):
    work_station = choose_workstation(ride)

    if work_station:
        try:
            ride.station = work_station.station
            ride.change_status(old_status=PENDING, new_status=ASSIGNED) # calls save()

            # emit signal

        except UpdateStatusError:
            logging.error("Cannot assign ride: %d" % ride.id)



def choose_workstation(ride):
    return WorkStation.by_id(3010) # always return amir_station_1_workstation_1