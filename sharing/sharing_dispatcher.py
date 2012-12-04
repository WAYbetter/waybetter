import traceback
from django.conf import settings
from google.appengine.ext import deferred
from common.tz_support import default_tz_now
from common.util import notify_by_email
from django.http import HttpResponse
from ordering.enums import RideStatus
from ordering.models import  SharedRide, Station
from datetime import timedelta
from pricing.models import RuleSet
import logging

DISPATCHING_TIME = timedelta(hours=24)

START_MONITORING_TIME = timedelta(minutes=60)
STOP_MONITORING_TIME = timedelta(minutes=10)

WS_SHOULD_HANDLE_TIME = 12  # minutes

SHOULD_VIEW_TIME = timedelta(minutes=9)
SHOULD_ACCEPT_TIME = timedelta(minutes=7)
SHOULD_ASSIGN_TIME = timedelta(minutes=4)
MUST_ACCEPT_TIME = timedelta(minutes=5)
MARK_COMPLETE_TIME = timedelta(hours=1)

def dispatching_cron(request):
    from sharing.station_controller import send_ride_in_risk_notification

    rides_to_dispatch = SharedRide.objects.filter(debug=settings.DEV, status=RideStatus.PENDING, depart_time__lte=default_tz_now() + DISPATCHING_TIME)
    logging.info(u"cron: dispatch rides: %s" % rides_to_dispatch)
    for ride in rides_to_dispatch:
        deferred.defer(dispatch_ride, ride)

    rides_to_monitor = SharedRide.objects.filter(debug=settings.DEV, depart_time__gte=default_tz_now() - START_MONITORING_TIME, depart_time__lte=default_tz_now() + STOP_MONITORING_TIME, status__in=[RideStatus.PROCESSING, RideStatus.ACCEPTED, RideStatus.PENDING, RideStatus.ASSIGNED, RideStatus.VIEWED])
    logging.info(u"cron: monitored rides: %s" % rides_to_monitor)
    for ride in rides_to_monitor:
        if default_tz_now() - ride.depart_time >= MUST_ACCEPT_TIME and ride.status != RideStatus.ACCEPTED:
            ride.change_status(new_status=RideStatus.FAILED)
        elif ride.depart_time <= default_tz_now() + SHOULD_ASSIGN_TIME and not ride.taxi_number:
            send_ride_in_risk_notification(u"Ride was not assigned to a taxi", ride.id)
        elif ride.depart_time <= default_tz_now() + SHOULD_ACCEPT_TIME and ride.status != RideStatus.ACCEPTED:
            send_ride_in_risk_notification(u"Ride was not accepted by station", ride.id)
        elif ride.depart_time <= default_tz_now() + SHOULD_VIEW_TIME and ride.status not in [RideStatus.VIEWED, RideStatus.ACCEPTED]:
            send_ride_in_risk_notification(u"Ride was not viewed by dispatcher", ride.id)

    rides_to_complete = SharedRide.objects.filter(debug=settings.DEV, status=RideStatus.ACCEPTED, depart_time__lte=default_tz_now() - MARK_COMPLETE_TIME)
    for ride in rides_to_complete:
        if not ride.change_status(old_status=RideStatus.ACCEPTED, new_status=RideStatus.COMPLETED):
            logging.error(u"ride [%s] was not marked COMPLETED" % ride.id)

    return HttpResponse("OK")


def dispatch_ride(ride):
    logging.info(u"dispatch ride [%s]" % ride.id)

    if not ride.change_status(old_status=RideStatus.PENDING, new_status=RideStatus.PROCESSING):
        logging.warning(u"Ride dispatched twice: %s" % ride.id)
        return # nothing to do.

    try:
        station = assign_ride(ride)
    except Exception, e:
        logging.error("assign ride raised exception: %s" % traceback.format_exc())
        station = None

    if not station:
        from sharing.station_controller import send_ride_in_risk_notification

        #TODO_WB: how do we handle this? cancel the orders?
        ride.change_status(old_status=RideStatus.PROCESSING, new_status=RideStatus.PENDING)
        send_ride_in_risk_notification(u"No station found for ride: %s" % ride.id, ride.id)


def assign_ride(ride, force_station=None):
    station = force_station or choose_station(ride)
    assigned_station = None

    logging.info(u"assigning ride [%s] to station: %s" % (ride.id, station))
    if station:
        try:
            ride.station = station
            ride.dn_fleet_manager_id = station.fleet_manager_id
            if force_station and ride.change_status(new_status=RideStatus.ASSIGNED): # calls save()
                assigned_station = station
            elif ride.change_status(old_status=RideStatus.PROCESSING, new_status=RideStatus.ASSIGNED): # calls save()
                assigned_station = station

        except Exception:
            notify_by_email(u"Cannot assign ride [%s]" % ride.id, msg="%s\n%s" % (ride.get_log(), traceback.format_exc()))

    if assigned_station:
        ride.update_cost()
        logging.info(u"ride[%s] was successfully assigned to station %s" % (ride.id, assigned_station))
        return assigned_station

    return None


def choose_station(ride):
    tariff = RuleSet.get_active_set(ride.depart_time)

    pricing_model_names = ride.cost_data.model_names_for_tariff(tariff)
    logging.info(u"found pricing models: %s" % u",".join([unicode(model_name) for model_name in pricing_model_names]))

    stations = Station.objects.filter(pricing_model_name__in=pricing_model_names)
    logging.info(u"found stations: %s" % u",".join([unicode(station.name) for station in stations]))

    # make sure debug and real orders don't mix
    stations = filter(lambda station: station.debug == ride.debug, stations)

    logging.info(u"stations list: %s" % u",".join([unicode(station.name) for station in stations]))

    if stations:
        return stations[0]

    else:
        logging.error(u"No sharing stations found %s" % ride.get_log())
        return None
