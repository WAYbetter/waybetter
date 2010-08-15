#from ordering.views import OrderError
from ordering.models import OrderAssignment, WorkStation
from ordering.station_connection_manager import is_workstation_available
from ordering.errors import OrderError
import models

def assign_order(order):
    work_station = choose_workstation(order)
    if not work_station:
        raise OrderError("Could not find a valid station")

    # create an OrderAssignment
    assignment = OrderAssignment()
    assignment.order = order
    assignment.station = work_station.station
    assignment.work_station = work_station
    assignment.save()

    return assignment


    
def choose_workstation(order):
    rejected_work_stations_ids = [order_assignment.work_station.id for order_assignment in OrderAssignment.objects.filter(order = order, status__in=[models.REJECTED, models.IGNORED])]
    if rejected_work_stations_ids == []:
        work_stations = WorkStation.objects.all()
    else:
        work_stations = WorkStation.objects.exclude(id__in=rejected_work_stations_ids)
        
    for ws in work_stations:
        if is_workstation_available(ws):
            return ws

    return None

    
    
