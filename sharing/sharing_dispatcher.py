import traceback
from google.appengine.ext import deferred
from common.tz_support import default_tz_now
from common.util import notify_by_email
from django.utils import translation
from django.utils.translation import ugettext as _
from django.http import HttpResponse
from ordering.enums import RideStatus
from ordering.models import  SharedRide, Station
from datetime import timedelta
from ordering.util import send_msg_to_passenger
from pricing.models import RuleSet
from sharing.algo_api import AlgoField
import logging

DISPATCHING_TIME = timedelta(hours=24)

def dispatching_cron(request):
    rides_to_dispatch = SharedRide.objects.filter(status=RideStatus.PENDING, depart_time__lte=default_tz_now() + DISPATCHING_TIME)
    logging.info("cron: dispatch rides: %s" % rides_to_dispatch)
    for ride in rides_to_dispatch:
        deferred.defer(dispatch_ride, ride)

    return HttpResponse("OK")


def dispatch_ride(ride):
    logging.info("dispatch ride [%s]" % ride.id)

    if not ride.change_status(old_status=RideStatus.PENDING, new_status=RideStatus.PROCESSING):
        logging.warning("Ride dispatched twice: %s" % ride.id)
        return # nothing to do.

    station = assign_ride(ride)
    if not station:
        from sharing.station_controller import send_ride_in_risk_notification

        #TODO_WB: how do we handle this? cancel the orders?
        ride.change_status(old_status=RideStatus.PROCESSING, new_status=RideStatus.PENDING)
        send_ride_in_risk_notification(u"No station found for ride: %s" % ride.id, ride.id)


def assign_ride(ride):
    station = choose_station(ride)
    logging.info("ride [%s] was assigned to station: %s" % (ride.id, station))
    if station:
        try:
            ride.station = station
            ride.dn_fleet_manager_id = station.fleet_manager_id
            if ride.change_status(old_status=RideStatus.PROCESSING, new_status=RideStatus.ASSIGNED): # calls save()
                return station

        except Exception:
            notify_by_email(u"Cannot assign ride [%s]" % ride.id, msg="%s\n%s" % (ride.get_log(), traceback.format_exc()))

    return None


def choose_station(ride):
    logging.info("ride cost data: %s" % ride.cost_data)
    cost_models = []
    tariffs = RuleSet.objects.all()
    for tariff in tariffs:
        if tariff.is_active(ride.depart_time.date(), ride.depart_time.time()):
            cost_models = ride.cost_data.get(tariff.tariff_type)
            break

    stations = []
    if cost_models:
        for cost_model in cost_models:
            pricing_model_name = cost_model[AlgoField.MODEL_ID]
            pricing_model_stations = Station.objects.filter(pricing_model_name=pricing_model_name)
            stations += pricing_model_stations
            logging.info("%s pricing model found stations: %s" % (pricing_model_name, pricing_model_stations))


#    ws_list = [ws for station in stations for ws in station.work_stations.filter(accept_shared_rides=True)]

    if ride.debug:
        logging.info("filtering debug ws")
        stations = filter(lambda station: station.accept_debug, stations)

    logging.info("stations list: %s" % stations)

    if stations:
        return stations[0]

    else:
        logging.error(u"No sharing stations found %s" % ride.get_log())
        return None
