import logging
import traceback
import pickle
from django.conf import settings
from google.appengine.api import memcache
from fleet.models import FleetManager, FleetManagerRideStatus
from ordering.models import SharedRide, ASSIGNED, COMPLETED, CANCELLED

MEMCACHE_NAMESPACE = "fleet_manager"

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

def update_ride_status(ride_id, status):
    """

    @param ride_id:
    @param status: A C{FleetManagerRideStatus}
    """
    wb_ride = SharedRide.by_id(ride_id)
    if status == FleetManagerRideStatus.COMPLETED:
        wb_ride.change_status(new_status=COMPLETED)
        logging.info("ride [%s] completed" % wb_ride.id)
        # expire cached taxi position for ride
    elif status == FleetManagerRideStatus.CANCELLED:
        wb_ride.change_status(new_status=CANCELLED)
        logging.info("ride [%s] cancelled" % wb_ride.id)
        # expire cached taxi position for ride
    else:
        logging.info("ride [%s] not updated to status %s" % (wb_ride.id, status))

def update_rides_position(ride_positions):
    """
    @param ride_positions: A list of {ride_id: Number, lat: Float, lon: Float, timestamp: datetime.datetime} dictionaries
    """
    _get_key = lambda rp: 'ride_%s' % rp["ride_id"]
    _get_val = lambda rp: pickle.dumps(rp)

    mapping = dict([(_get_key(rp), _get_val(rp)) for rp in ride_positions])
    memcache.set_multi(mapping, namespace=MEMCACHE_NAMESPACE)


def get_ride_position(ride_id):
    cached_position = memcache.get('position_%s' % ride_id, namespace=MEMCACHE_NAMESPACE)
    if cached_position:
        cached_position = pickle.loads(cached_position)

    return cached_position


def get_ongoing_rides(fm_id=None):
    logging.info("get ongoing rides for fleet backend [%s]" % fm_id)
    rides = SharedRide.objects.filter(status=ASSIGNED)
    if fm_id:
        rides = filter(lambda r: r.dn_fleet_manager_id == fm_id, rides)

    return rides


#########################################
## OVERRIDE SOME METHODS FOR DEBUGGING ##
#########################################

if settings.DEV:
    # debug rides created by isr_tests.py are not stored in the db but in memory
    DEV_WB_ONGOING_RIDES = []
    DEV_WB_COMPLETED_RIDES = []

    def get_ongoing_rides(fm_id=None):
        logging.info("get ongoing rides for fleet backend [%s]" % fm_id)
        return DEV_WB_ONGOING_RIDES

    def update_ride_status(wb_ride, status):
        if status == FleetManagerRideStatus.COMPLETED:
            DEV_WB_COMPLETED_RIDES.append(wb_ride)
            # remove from DEV_WB_ONGOING_RIDES
            for i, r in enumerate(DEV_WB_ONGOING_RIDES):
                if r.id == wb_ride.id:
                    DEV_WB_ONGOING_RIDES.pop(i)
                    break
            logging.info("ride [%s] completed" % wb_ride.id)
        elif status == FleetManagerRideStatus.CANCELLED:
            logging.info("ride [%s] cancelled" % wb_ride.id)