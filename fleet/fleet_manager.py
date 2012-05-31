import logging
import traceback
import pickle
from django.conf import settings
from google.appengine.api import memcache
from fleet.models import FleetManager, FleetManagerRideStatus
from ordering.models import SharedRide, ASSIGNED, COMPLETED
import signals as fleet_signals

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
    rides = SharedRide.objects.filter(status=ASSIGNED)
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
    wb_ride = SharedRide.by_id(fmr.id)
    if not wb_ride:
        logging.error("fleet manager: fmr update to non-existing ride")
        return
    if fmr.status == FleetManagerRideStatus.COMPLETED:
        wb_ride.change_status(new_status=COMPLETED)
    else:
        logging.info("fleet manager: ride [%s] not updated. fmr_status=%s raw_status=%s)" %
                     (wb_ride.id, FleetManagerRideStatus.get_name(fmr.status), fmr.raw_status))


FM_MEMCACHE_NAMESPACE = "fm_ns"
_get_key = lambda ride_id: 'position_%s' % ride_id
_get_key_rp = lambda rp: _get_key(rp.ride_id)
_get_val = lambda rp: pickle.dumps(rp)
def update_positions(ride_positions):
    """
    Handler for fleet backends to call when taxi positions changes. Sends the signals and stores the data in memcache.
    @param ride_positions: A list of C{TaxiRidePosition}
    """
    logging.info("fleet manager: positions update %s" % [rp.taxi_id for rp in ride_positions])
    fleet_signals.positions_update_signal.send(sender="fleet_manager", positions=ride_positions)

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


#########################################
## OVERRIDE SOME METHODS FOR DEBUGGING ##
#########################################

if settings.DEV:
    # debug rides created by isr_tests.py are not stored in the db but in memory
    def get_ongoing_rides(backend=None):
        from isr_tests import DEV_WB_ONGOING_RIDES, DEV_WB_COMPLETED_RIDES
        logging.info("get ongoing rides for fleet %s: %s" % (backend.name if backend else "ALL", DEV_WB_ONGOING_RIDES))
        return DEV_WB_ONGOING_RIDES

    def update_ride(fmr):
        from isr_tests import DEV_WB_ONGOING_RIDES, DEV_WB_COMPLETED_RIDES

        logging.info("fleet manager DEV: ride update %s" % fmr)
        fleet_signals.fmr_update_signal.send(sender="fleet_manager", fmr=fmr)

        wb_ride = None
        wb_ride_idx = None
        for i, r in enumerate(DEV_WB_ONGOING_RIDES):
            if r.id == fmr.id:
                wb_ride = DEV_WB_ONGOING_RIDES[i]
                wb_ride_idx = i
                break

        if fmr.status == FleetManagerRideStatus.COMPLETED:
            if wb_ride:
                from sharing.signals import ride_status_changed_signal
                ride_status_changed_signal.send(sender="fleet_manager", obj=wb_ride, status=COMPLETED)
                DEV_WB_ONGOING_RIDES.pop(wb_ride_idx)
                DEV_WB_COMPLETED_RIDES.append(wb_ride)