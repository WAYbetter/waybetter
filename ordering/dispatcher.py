#from ordering.views import OrderError
import logging
from google.appengine.api import memcache
from ordering.models import OrderAssignment, Station, WorkStation
from ordering.signals import orderassignment_created_signal
from ordering.station_connection_manager import is_workstation_available
from ordering.errors import  NoWorkStationFoundError, UpdateStatusError
import models
from common.util import log_event, EventType
from common.langsupport.util import translate_address_for_ws


def assign_order(order):
    """
    Assign the order to a workstation and return the assignment.
    """
    passenger = order.passenger
    work_station = choose_workstation(order)
    if not work_station:
        raise NoWorkStationFoundError("Could not find a valid station")

    # create an OrderAssignment
    assignment = OrderAssignment(order=order, station=work_station.station, work_station=work_station)
    assignment.pickup_address_in_ws_lang = translate_address_for_ws(work_station, order, 'from')
    assignment.dropoff_address_in_ws_lang = translate_address_for_ws(work_station, order, 'to')

    # de-normalize business name
    if passenger.business:
        assignment.business_name = passenger.business.name

    assignment.save()

    work_station.last_assignment_date = assignment.create_date
    work_station.save()
    work_station.station.last_assignment_date = assignment.create_date
    work_station.station.save()

    try:
        order.change_status(new_status=models.ASSIGNED)
        log_event(EventType.ORDER_ASSIGNED,
                  passenger=passenger,
                  order=order,
                  order_assignment=assignment,
                  station=work_station.station,
                  work_station=work_station)
        # emit the signal only if the order was successfully marked as ASSIGNED
        orderassignment_created_signal.send(sender="orderassignment_created_signal", obj=assignment)
    except UpdateStatusError:
        logging.error("Cannot assign order: %d" % order.id)

    return assignment


def choose_workstation(order):
    ws_list_key = 'ws_list_for_order_%s' % order.id
    ws_list = memcache.get(ws_list_key) or []
    if not ws_list:
        ws_list = compute_ws_list(order)


    # remove work stations whose station rejected/ignored this order
    rejected_station_ids = [order_assignment.station.id for order_assignment in
                            OrderAssignment.objects.filter(order=order, status__in=[models.REJECTED, models.IGNORED])]
    rejected_ws_ids = [ws.id for ws in WorkStation.objects.filter(dn_station_id__in= rejected_station_ids)]

    for ws in rejected_ws_ids:
        if ws in ws_list:
            ws_list.remove(ws) # assumes a work station appears at most once

    if ws_list:
        ws = ws_list.pop(0)
        memcache.set(ws_list_key, ws_list)
        logging.info("next ws is: %s" % ws)
        return ws

    return None


def compute_ws_list(order):
    """
    Compute workstation list, ignoring those who have previously rejected or ignored the order.
    """
    if order.confining_station:
        ws_qs = order.confining_station.work_stations.all()
    else:
        ws_qs = WorkStation.objects.all()


    # exclude work station whose station rejected/ignored this order
    rejected_station_ids = [order_assignment.station.id for order_assignment in
                       OrderAssignment.objects.filter(order=order, status__in=[models.REJECTED, models.IGNORED])]
    rejected_ws_ids = [ws.id for ws in WorkStation.objects.filter(dn_station_id__in= rejected_station_ids)]

    if rejected_ws_ids:
        ws_qs = ws_qs.exclude(id__in=rejected_ws_ids)

    # exclude work stations that don't accept orders
    ws_qs = ws_qs.exclude(accept_orders=False)

    station_list = []
    originating_ws = []
    default_ws = []
    first_round_ws = []
    second_round_ws = []

    # originating station is first, default station is second then the rest of the stations ordered by distance from order
    for ws in sorted(ws_qs, key=lambda ws: ws.station.distance_from_order(order=order, to_pickup=True, to_dropoff=False)):
        station = ws.station

        if is_workstation_available(ws) and station.is_in_valid_distance(order=order):
            if station == order.originating_station:
                originating_ws.append(ws)
            elif station == order.passenger.default_station:
                default_ws.append(ws)
            else:
                if station in station_list:
                    second_round_ws.append(ws)
                else:
                    first_round_ws.append(ws)
                    station_list.append(station)


    # assuming that a work station appears exactly once in every sub list
    ws_list = originating_ws + default_ws + first_round_ws + second_round_ws

    log = "computing ws list:\n"
    for ws in ws_list:
        log += "station: %s, ws id:%d\n" % (ws.dn_station_name, ws.id)
    logging.info(log)
    
    return ws_list