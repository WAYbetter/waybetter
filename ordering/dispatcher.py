#from ordering.views import OrderError
from google.appengine.api import memcache
from ordering.models import OrderAssignment, WorkStation
from ordering.station_connection_manager import is_workstation_available
from ordering.errors import  NoWorkStationFoundError
import models
from common.util import log_event, EventType
from common.langsupport.util import translate_pickup_for_ws


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
    ws_list_key = 'ws_list_for_order_%s' % order.id
    ws_list = memcache.get(ws_list_key) or []
    if not ws_list:
        ws_list = compute_ws_list(order)

    if ws_list:
        ws = ws_list.pop(0)
        memcache.set(ws_list_key, ws_list)
        return ws

    return None
    
def compute_ws_list(order):
    """
    Compute workstation list, ignoring those who have previously rejected or ignored the order.
    """
    # TODO_WB: iterate stations and not work stations
    rejected_ws_ids = [order_assignment.work_station.id for order_assignment in OrderAssignment.objects.filter(order = order, status__in=[models.REJECTED, models.IGNORED])]

    if not rejected_ws_ids:
        ws_qs = WorkStation.objects.all()
    else:
        ws_qs = WorkStation.objects.exclude(id__in=rejected_ws_ids)

    ws_qs = ws_qs.exclude(accept_orders=False)
    ws_list = []
    station_list=[]

    # originating station is first, default station is second then the rest
    for station in [order.originating_station, order.passenger.default_station]:
        if station and station.is_in_valid_distance(order=order):
            for ws in ws_qs.filter(station=station):
                if is_workstation_available(ws):
                    ws_list.append(ws)
                    station_list.append(station)
                    break

    # then the rest of the stations (one work station each) ordered by distance from order
    for ws in sorted(ws_qs, key=lambda ws: ws.station.distance_from_order(order=order)):
        station = ws.station
        if station in station_list:
            # TODO_WB: do not skip ws
            continue
        if station.is_in_valid_distance(order=order):
            for ws in ws_qs.filter(station=station):
                if is_workstation_available(ws):
                    ws_list.append(ws)
                    station_list.append(station)
                    break

    return ws_list