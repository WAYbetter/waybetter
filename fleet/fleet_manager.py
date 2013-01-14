# -*- coding: utf-8 -*-

from datetime import timedelta
import logging
import re
import traceback
import pickle
from google.appengine.api import memcache
from common.geo_calculations import distance_between_points
from common.tz_support import default_tz_now
from common.util import get_uuid
from fleet.models import FleetManager, FleetManagerRideStatus
from ordering.models import RideEvent, PickMeAppRide, SharedRide, BaseRide, StopType
import signals as fleet_signals

POSITION_CHANGED = "Position Changed"
DISTANCE_CONSIDERED_AS_VISITED_IN_METERS = 70

def create_ride(ride):
    try:
        station = ride.station
        assert station, "ride [%s] is not assigned to a station" % ride.id
        assert station.fleet_station_id, "station %s has no fleet_station_id" % ride.station.name
        assert ride.dn_fleet_manager_id, "ride [%s] is not associated with a fleet manager" % ride.id

        # refresh uuid so that we can re-insert this ride into fleet_manager db without conflict
        ride.update(uuid=get_uuid())

        ride_fm = FleetManager.by_id(ride.dn_fleet_manager_id)
        result = ride_fm.create_ride(ride, ride.station, taxi_number=ride.taxi_number)
        return bool(result)
    except Exception, e:
        logging.error(traceback.format_exc())
        return False


def cancel_ride(ride):
    try:
        assert ride.dn_fleet_manager_id, "ride [%s] is not associated with a fleet manager" % ride.id
        ride_fm = FleetManager.by_id(ride.dn_fleet_manager_id)
        result = ride_fm.cancel_ride(ride.uuid)
        return bool(result)
    except Exception, e:
        logging.error(traceback.format_exc())
        return False


def get_ride(ride):
    try:
        assert ride.dn_fleet_manager_id, "ride [%s] is not associated with a fleet manager" % ride.id
        ride_fm = FleetManager.by_id(ride.dn_fleet_manager_id)
        fmr = ride_fm.get_ride(ride.id)
        return fmr
    except Exception, e:
        logging.error(traceback.format_exc())
        return None


def get_ongoing_rides(backend=None):
    delta = default_tz_now() - timedelta(minutes=15)
    pickmeapp_rides = list(PickMeAppRide.objects.filter(arrive_time__gt=delta))
    shared_rides = list(SharedRide.objects.filter(arrive_time__gt=delta))

    rides = pickmeapp_rides + shared_rides
    if backend:
        rides = filter(lambda r: r.dn_fleet_manager_id == backend.id, rides)

    logging.info("get ongoing rides for fleet %s: %s" % (backend.name if backend else "ALL", rides))
    return rides

def send_message(ride, message):
    logging.info(u"send_message '%s' to ride: %s" % (message, ride.id))
    try:
        station = ride.station
        assert station, "ride [%s] is not assigned to a station" % ride.id
        assert station.fleet_station_id, "station %s has no fleet_station_id" % ride.station.name
        assert ride.dn_fleet_manager_id, "ride [%s] is not associated with a fleet manager" % ride.id
        assert ride.taxi_number, "ride [%s] is not associated with a taxi number" % ride.id

        ride_fm = FleetManager.by_id(ride.dn_fleet_manager_id)
        result = ride_fm.send_message(message, ride.station.fleet_station_id, ride.taxi_number)

        # log a RideEvent about his message
        rp = get_ride_position(ride)
        e = RideEvent(pickmeapp_ride=None, shared_ride=ride,
                      status=FleetManagerRideStatus.MESSAGE_SENT, raw_status=message, lat=rp.lat if rp else None, lon=rp.lon if rp else None, taxi_id=ride.taxi_number, timestamp=default_tz_now())
        e.save()

        return result
    except Exception, e:
        logging.error(traceback.format_exc())
        return False


def send_ride_point_text(ride, ride_point, next_point=None):
    def _passengers_line(passengers, show_phones=True):
        if show_phones:
            if len(passengers) > 2:
                return u", ".join([p.phone for p in passengers])
            else:
                return u", ".join([u"%s %s" % (p.phone, p.name[:7]) for p in passengers])
        else:
            return u", ".join([p.name[:10] for p in passengers])

    def _clean_address(address):
        return re.sub(u",?\s+תל אביב יפו", u" תא", address).replace(u" - ", u" ")

    def _address_line(ride_points, ride_point):
        if ride_point == ride_points[-1]:
            address_type = u"סיום"
        else:
            address_type = u"איסוף" if ride_point.type == StopType.PICKUP else u"הורדה"

        address = (u"%s %s" % (address_type, _clean_address(ride_point.address)))[0:29]

        return u"%s.%s %s" % (ride_points.index(ride_point) + 1, address, ride_point.stop_time.strftime("%H:%M"))

    ride_points = list(ride.points.all().order_by("stop_time"))
    is_first = ride_point == ride_points[0]
    passengers = ride_point.passengers
    ride_point.update(dispatched=True)

    message = u"ווי בטר- %g שח הפתק בתחנה- %s כתובות:\n" % (ride.cost, len(ride_points)) if is_first else u""
    message += u"%s\n" % _address_line(ride_points, ride_point)
    message += u"%s\n" % _passengers_line(passengers, show_phones=(ride_point.type==StopType.PICKUP))
    message += _address_line(ride_points, next_point)

    return send_message(ride, message)

def update_ride(fmr):
    """
    Update our db with ride data from a fleet manager.
    @param fmr: A C{FleetMangerRide} containing updated data about the ride.
    """
    logging.info("fleet manager: ride update %s" % fmr)
    fleet_signals.fmr_update_signal.send(sender="fleet_manager", fmr=fmr)

    pickmeapp_ride, shared_ride = rides_from_uuid(fmr.id)
    if not (pickmeapp_ride or shared_ride):
        logging.error("fleet manager: fmr update to non-existing ride")
        return

    e = RideEvent(pickmeapp_ride=pickmeapp_ride, shared_ride=shared_ride, status=fmr.status, raw_status=fmr.raw_status,
                  lat=fmr.lat, lon=fmr.lon, taxi_id=fmr.taxi_id, timestamp=fmr.timestamp)
    e.save()

    # TODO_WB: update wb_ride when we trust ISR data
    wb_ride = pickmeapp_ride or shared_ride
    logging.info("fleet manager: ride [%s] not updated. fmr_status=%s raw_status=%s)" %
                 (wb_ride.id, FleetManagerRideStatus.get_name(fmr.status), fmr.raw_status))

FM_MEMCACHE_NAMESPACE = "fm_ns"
_get_key = lambda ride_uuid: 'position_%s' % ride_uuid

def update_positions(ride_positions):
    """
    Handler for fleet backends to call when taxi positions changes. Sends the signals and stores the data in memcache.
    @param ride_positions: A list of C{TaxiRidePosition}
    """
    logging.info("fleet manager: positions update %s" % [rp.ride_uuid for rp in ride_positions])
    fleet_signals.positions_update_signal.send(sender="fleet_manager", positions=ride_positions)

    for rp in ride_positions:
        key = _get_key(rp.ride_uuid)
        logging.info("getting from memcache: %s, %s" % (key, FM_MEMCACHE_NAMESPACE))
        cached_rp = memcache.get(key, namespace=FM_MEMCACHE_NAMESPACE)
        if cached_rp:
            logging.info("memcache[%s] -> %s" % (key, pickle.loads(cached_rp).__dict__))

        pickled_rp = pickle.dumps(rp)
        if cached_rp != pickled_rp: # this is a new position
            logging.info("new position received: %s[%s:%s]" % (rp.ride_uuid, rp.lat, rp.lon))
            memcache.set(key, pickled_rp, namespace=FM_MEMCACHE_NAMESPACE)

            pickmeapp_ride, shared_ride = rides_from_uuid(rp.ride_uuid)
            if pickmeapp_ride or shared_ride:
                e = RideEvent(pickmeapp_ride=pickmeapp_ride, shared_ride=shared_ride,
                              status=FleetManagerRideStatus.POSITION_CHANGED, raw_status=POSITION_CHANGED, lat=rp.lat,
                              lon=rp.lon, taxi_id=rp.taxi_id, timestamp=rp.timestamp)
                e.save()
                logging.info("new ride event created: %s" % e)
            if shared_ride:
                for point in shared_ride.points.all():
                    distance = distance_between_points(point.lat, point.lon, rp.lat, rp.lon) * 1000
                    if distance <= DISTANCE_CONSIDERED_AS_VISITED_IN_METERS:
                        point.update(visited=True)
                        logging.info("%s %s visited" % (point.get_type_display(), point.id))
        else:
            logging.info("old position received: %s[%s:%s]" % (rp.ride_uuid, rp.lat, rp.lon))

def get_ride_position(ride):
    """
    Get the latest known taxi position for a ride.
    @param ride: ride to track
    @return: A C{TaxiRidePosition} or None
    """
    trp = None
    cached_trp = memcache.get(_get_key(ride.uuid), namespace=FM_MEMCACHE_NAMESPACE)
    if cached_trp:
        trp = pickle.loads(cached_trp)
        logging.info("found position for ride: %s" % ride.uuid)
        logging.info("position.timestamp = %s, stale? = %s" % (trp.timestamp, (trp.timestamp < default_tz_now() - timedelta(minutes=15))))
    else:
        logging.warning("no position found position for ride: %s" % ride.uuid)

    return trp

def rides_from_uuid(ride_uuid):
    ride = BaseRide.by_uuid(ride_uuid)
    pickmeapp_ride = ride if isinstance(ride, PickMeAppRide) else None
    shared_ride = ride if isinstance(ride, SharedRide) else None

    return pickmeapp_ride, shared_ride
