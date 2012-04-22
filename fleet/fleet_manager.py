import logging
import traceback
import pickle
from django.conf import settings
from google.appengine.api import memcache
from fleet.models import FleetManager, FleetManagerRideStatus
from ordering.models import SharedRide, ASSIGNED, COMPLETED, CANCELLED

MEMCACHE_NAMESPACE = "fleet_manager"

def create_ride(ride):
    station = ride.station
    assert station, "ride [%s] is not assigned to a station" % ride.id
    assert station.fleet_station_id, "station %s has no fleet_station_id" % ride.station.name
    assert ride.dn_fleet_manager_id, "ride [%s] is not associated with a fleet manager" % ride.id

    try:
        ride_fm = FleetManager.by_id(ride.dn_fleet_manager_id)
        return ride_fm.create_ride(ride, ride.station)
    except Exception, e:
        logging.error(traceback.format_exc())

def get_wb_ongoing_rides():
    return SharedRide.objects.filter(status=ASSIGNED)

def query_backends():
    wb_ongoing_rides = get_wb_ongoing_rides()
    wb_ongoing_rides_map = dict([(ride.id, ride) for ride in wb_ongoing_rides])

    fm_ids = set([ride.dn_fleet_manager_id for ride in wb_ongoing_rides])
    fm_backends = FleetManager.objects.filter(id__in=fm_ids)

    fm_ongoing_rides = []
    for fm_backend in fm_backends:
        try:
            logging.info("querying fleet manager backend %s" % fm_backend.name)
            fm_ongoing_rides += fm_backend.get_ongoing_rides()
        except Exception, e:
            logging.error("failed querying backend %s: %s" % (fm_backend.name, traceback.format_exc()))

    logging.info("waybetter ongoing rides: %s" % wb_ongoing_rides)
    logging.info("fleet manager ongoing rides: %s" % fm_ongoing_rides)

    set_fmr(fmrs=fm_ongoing_rides)

    for fmr in fm_ongoing_rides:
        wb_ride = wb_ongoing_rides_map.pop(fmr.id, None)
        if wb_ride:
            update_from_fmr(wb_ride, fmr)
        else:
            logging.error("ride [%s] considered ongoing by fleet manager backend but not by us" % fmr.id)

    # rides we consider ongoing but not returned by backends; query individually.
    for wb_ride in wb_ongoing_rides_map.values():
        logging.info("ride [%s] not returned by backends, querying individually..." % wb_ride.id)
        try:
            fm_backend = filter(lambda fm: fm.id == wb_ride.dn_fleet_manager_id, fm_backends)[0]
            fmr = fm_backend.get_ride(wb_ride.id)
            update_from_fmr(wb_ride, fmr)
            set_fmr(fmr=fmr)
        except IndexError, e:
            logging.error("fm backend not in backends list")
        except BaseException, e:
            #noinspection PyUnboundLocalVariable
            logging.error("failed querying backend %s for ride [%s]: %s" % (fm_backend.name, wb_ride.id, traceback.format_exc()))


def update_from_fmr(wb_ride, fmr):
    """ Update a WAYbetter C{SharedRide} from a C{FleetManagerRide}.
    """
    assert wb_ride.id == fmr.id, "update from fmr failed: ids do not match (%s != %s)" % (wb_ride.id, fmr.id)
    if fmr.status == FleetManagerRideStatus.COMPLETED:
        wb_ride.change_status(new_status=COMPLETED)
        logging.info("ride [%s] completed" % wb_ride.id)
    elif fmr.status == FleetManagerRideStatus.CANCELLED:
        wb_ride.change_status(new_status=CANCELLED)
        logging.info("ride [%s] cancelled" % wb_ride.id)
    else:
        logging.info("ride [%s] not updated: %s [%s]" % (wb_ride.id, fmr.status, fmr.raw_status))


def set_fmr(fmr=None, fmrs=None):
    _get_key = lambda fmr: 'fmr_%s' % fmr.id
    _get_val = lambda fmr: pickle.dumps(fmr)

    if fmr:
        memcache.set(_get_key(fmr), _get_val(fmr), namespace=MEMCACHE_NAMESPACE)
    if fmrs:
        mapping = dict([(_get_key(fmr), _get_val(fmr)) for fmr in fmrs])
        memcache.set_multi(mapping, namespace=MEMCACHE_NAMESPACE)

def get_fmr(ride_id):
    """ Return C{FleetManagerRide} containing info about the ride.
    @param ride_id:
    @return: C{FleetManagerRide} or None
    """
    fmr_data = memcache.get('fmr_%s' % ride_id, namespace=MEMCACHE_NAMESPACE)
    fmr = pickle.loads(fmr_data) if fmr_data else None
    return fmr


#########################################
## OVERRIDE SOME METHODS FOR DEBUGGING ##
#########################################

if settings.DEV:
    # debug rides created by isr_tests.py are not stored in the db but in memory
    DEV_WB_ONGOING_RIDES = []
    DEV_WB_COMPLETED_RIDES = []

    def get_wb_ongoing_rides():
        return DEV_WB_ONGOING_RIDES

    def update_from_fmr(wb_ride, fmr):
        if fmr.status == FleetManagerRideStatus.COMPLETED:
            DEV_WB_COMPLETED_RIDES.append(wb_ride)
            # remove from DEV_WB_ONGOING_RIDES
            for i, r in enumerate(DEV_WB_ONGOING_RIDES):
                if r.id == wb_ride.id:
                    DEV_WB_ONGOING_RIDES.pop(i)
                    break
            logging.info("ride [%s] completed" % wb_ride.id)
        elif fmr.status == FleetManagerRideStatus.CANCELLED:
            logging.info("ride [%s] cancelled" % wb_ride.id)