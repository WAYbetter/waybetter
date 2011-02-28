#from ordering.views import OrderError
import logging
from ordering.models import OrderAssignment, WorkStation
from ordering.station_connection_manager import is_workstation_available
from ordering.errors import OrderError, NoWorkStationFoundError
from common.geo_calculations import distance_between_points
import models
from common.util import log_event, EventType, translate_pickup_for_ws
from datetime import datetime


def assign_order(order):
    """
    Assign the order to a workstation and return the assignment.
    """
    work_station = choose_workstation(order)
    if not work_station:
        raise NoWorkStationFoundError("Could not find a valid station")

    # create an OrderAssignment
    assignment = OrderAssignment()
    assignment.order = order
    assignment.station = work_station.station
    assignment.work_station = work_station
    assignment.pickup_address_in_ws_lang = translate_pickup_for_ws(work_station, order)
    assignment.save()

    work_station.last_assignment_date = assignment.create_date
    work_station.save()
    work_station.station.last_assignment_date = assignment.create_date
    work_station.station.save()

    order.status = models.ASSIGNED
    order.save()
    log_event(EventType.ORDER_ASSIGNED,
              passenger=order.passenger,
              order=order,
              order_assignment=assignment,
              station=work_station.station,
              work_station=work_station)
    
    return assignment


    
def choose_workstation(order):
    """
    Choose a nearby workstation, ignoring those who have previously rejected or ignored the order.
    """
    rejected_work_stations_ids = [order_assignment.work_station.id for order_assignment in OrderAssignment.objects.filter(order = order, status__in=[models.REJECTED, models.IGNORED])]
    if rejected_work_stations_ids == []:
        work_stations_qs = WorkStation.objects.all()
    else:
        work_stations_qs = WorkStation.objects.exclude(id__in=rejected_work_stations_ids)

    work_stations_qs = work_stations_qs.exclude(accept_orders=False)
    work_stations = []

    if order.originating_station:
        for ws in order.originating_station.work_stations.all():
            if is_workstation_available(ws) and \
                ws.station.is_in_valid_distance(order.from_lon, order.from_lat, order.to_lon, order.to_lat):
                return ws

    for ws in work_stations_qs:
        if is_workstation_available(ws) and \
           ws.station.is_in_valid_distance(order.from_lon, order.from_lat, order.to_lon, order.to_lat):
            work_stations.append(ws)


    work_stations = sorted(work_stations, key=lambda ws: ws.station.last_assignment_date)
    for ws in work_stations:
        if ws.station == order.passenger.default_station:
            return ws

    if work_stations:
        return work_stations[0] 

    return None