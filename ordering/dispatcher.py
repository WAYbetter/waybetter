#from ordering.views import OrderError
from ordering.models import OrderAssignment, WorkStation
from ordering.station_connection_manager import is_workstation_available
from ordering.errors import OrderError, NoWorkStationFoundError
from common.geo_calculations import distance_between_points
import models

MAX_STATION_DISTANCE_KM = 30

def assign_order(order):
    work_station = choose_workstation(order)
    if not work_station:
        raise NoWorkStationFoundError("Could not find a valid station")

    # create an OrderAssignment
    assignment = OrderAssignment()
    assignment.order = order
    assignment.station = work_station.station
    assignment.work_station = work_station
    assignment.save()

    order.status = models.ASSIGNED
    order.save()

    return assignment


    
def choose_workstation(order):
    rejected_work_stations_ids = [order_assignment.work_station.id for order_assignment in OrderAssignment.objects.filter(order = order, status__in=[models.REJECTED, models.IGNORED])]
    if rejected_work_stations_ids == []:
        work_stations_qs = WorkStation.objects.all()
    else:
        work_stations_qs = WorkStation.objects.exclude(id__in=rejected_work_stations_ids)

    work_stations_qs = work_stations_qs.exclude(accept_orders=False)
    work_stations = []

    for ws in work_stations_qs:
        if is_workstation_available(ws) and station_in_valid_distance(ws.station, order):
            work_stations.append(ws)


    for ws in work_stations:
        if ws.station == order.passenger.default_station:
            return ws

    if work_stations:
        return work_stations[0] 

    return None

def station_in_valid_distance(station, order):
    if not (station.lat and station.lon): # ignore station with unknown address
        return False

    return (distance_between_points(station.lat, station.lon, order.from_lat, order.from_lon) <= MAX_STATION_DISTANCE_KM or
        distance_between_points(station.lat, station.lon, order.to_lat, order.to_lon) <= MAX_STATION_DISTANCE_KM)

    
