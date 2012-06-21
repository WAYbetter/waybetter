from datetime import timedelta
import logging
import traceback
import pickle
from google.appengine.api import memcache
from common.tz_support import default_tz_now
from fleet.models import FleetManager, FleetManagerRideStatus
from ordering.models import RideEvent, Order, OrderType, PickMeAppRide, RidePoint
import signals as fleet_signals

POSITION_CHANGED = "Position Changed"

def create_ride(ride):
    try:
        station = ride.station
        assert station, "ride [%s] is not assigned to a station" % ride.id
        assert station.fleet_station_id, "station %s has no fleet_station_id" % ride.station.name
        assert ride.dn_fleet_manager_id, "ride [%s] is not associated with a fleet manager" % ride.id

        ride_fm = FleetManager.by_id(ride.dn_fleet_manager_id)
        result = ride_fm.create_ride(ride, ride.station)
        return bool(result)
    except Exception, e:
        logging.error(traceback.format_exc())
        return False

def cancel_ride(ride):
    try:
        assert ride.dn_fleet_manager_id, "ride [%s] is not associated with a fleet manager" % ride.id
        ride_fm = FleetManager.by_id(ride.dn_fleet_manager_id)
        result = ride_fm.cancel_ride(ride.id)
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
    an_hour_ago = default_tz_now() - timedelta(hours=1)
    pickmeapp_rides = list(PickMeAppRide.objects.filter(create_date__gt=an_hour_ago))
    points = RidePoint.objects.filter(stop_time__gt=an_hour_ago)
    shared_rides = list(set([p.ride for p in points]))

    rides = pickmeapp_rides + shared_rides
    if backend:
        rides = filter(lambda r: r.dn_fleet_manager_id == backend.id, rides)

    logging.info("get ongoing rides for fleet %s: %s" % (backend.name if backend else "ALL", rides))
    return rides

def update_ride(fmr):
    """
    Update our db with ride data from a fleet manager.
    @param fmr: A C{FleetMangerRide} containing updated data about the ride.
    """
    logging.info("fleet manager: ride update %s" % fmr)
    fleet_signals.fmr_update_signal.send(sender="fleet_manager", obj=fmr)

    pickmeapp_ride, shared_ride = rides_from_order_id(fmr.id)

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
_get_key = lambda ride_id: 'position_%s' % ride_id
_get_key_rp = lambda rp: _get_key(rp.order_id)
_get_val = lambda rp: pickle.dumps(rp)
def update_positions(ride_positions):
    """
    Handler for fleet backends to call when taxi positions changes. Sends the signals and stores the data in memcache.
    @param ride_positions: A list of C{TaxiRidePosition}
    """
    logging.info("fleet manager: positions update %s" % [rp.taxi_id for rp in ride_positions])
    fleet_signals.positions_update_signal.send(sender="fleet_manager", positions=ride_positions)

    for rp in ride_positions:
        pickmeapp_ride, shared_ride = rides_from_order_id(rp.order_id)

        if pickmeapp_ride or shared_ride:
            e = RideEvent(pickmeapp_ride=pickmeapp_ride, shared_ride=shared_ride, status=FleetManagerRideStatus.POSITION_CHANGED, raw_status=POSITION_CHANGED
                          ,
                              lat=rp.lat, lon=rp.lon, taxi_id=rp.taxi_id, timestamp=rp.timestamp)
            e.save()

    mapping = dict([(_get_key_rp(rp), _get_val(rp)) for rp in ride_positions])
    memcache.set_multi(mapping, namespace=FM_MEMCACHE_NAMESPACE)


def get_ride_position(ride_id):
    """
    Get the latest known taxi position for a ride.
    @param ride_id:
    @return: A C{TaxiRidePosition} or None
    """
    trp = None
    cached_trp = memcache.get(_get_key(ride_id), namespace=FM_MEMCACHE_NAMESPACE)
    if cached_trp:
        trp = pickle.loads(cached_trp)

    return trp


def rides_from_order_id(order_id):
    order = Order.by_id(order_id)
    if not order:
        logging.error("fleet manager: rides_from_order_id for non-existing order id=%s" % order_id)
        return None, None

    pickmeapp_ride, shared_ride = None, None
    if order.type == OrderType.PICKMEAPP:
        pickmeapp_ride = order.pickmeapp_ride
    else:
        shared_ride = order.ride

    return pickmeapp_ride, shared_ride
