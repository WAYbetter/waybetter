import datetime
from common.models import BaseModel
from django.db import models
from django.utils.importlib import import_module
from common.util import Enum

class FleetManagerRideStatus(Enum):
    PENDING = 0
    ASSIGNED_TO_TAXI = 1
    DRIVER_ACCEPTED = 2
    WAITING_FOR_PASSENGER = 3
    PASSENGER_PICKUP = 4
    PASSENGER_DROPOFF = 5
    PASSENGER_NO_SHOW = 6
    COMPLETED = 7
    CANCELLED = 8


class AbstractFleetManagerBackend(object):
    @classmethod
    def create_ride(cls, ride, station):
        """Create a ride on the fleet manager backend.
        @param ride: an C{ordering.SharedRide} instance.
        @param station: the C{Station} which will receive the ride.
        @return: a C{FleetManagerRide} instance, or None if creation failed.
        """
        raise NotImplementedError()

    @classmethod
    def cancel_ride(cls, ride_id):
        """Cancel a ride from the fleet manager backend.
        @param ride_id: the id of the wb ride to cancel.
        @return: True/False on success/fail.
        """
        raise NotImplementedError()

    @classmethod
    def get_ride(cls, ride_id):
        """Query the fleet manager for a ride.
        @param ride_id: the id of the wb ride to query
        @return: C{FleetManagerRide} or None
        """
        raise NotImplementedError()


class FleetManagerRide(object):
    def __init__(self, wb_id, status, taxi_id, lat, lon, timestamp, raw_status=None):
        """Constructor.
        @param wb_id: Long representing the id of the ride as recorded in our db.
        @param status: Number representing the status as one of C{FleetManagerRideStatus}.
        @param taxi_id: Number of the taxi assigned to this ride or None.
        @param lat: latitude of the taxi captured on C{timestamp} or None.
        @param lon: longitude of the taxi captured on C{timestamp} or None.
        @param timestamp: A datetime.datetime instance or None.
        @param raw_status: The original status as returned by the backend.
        """
        assert wb_id
        assert timestamp is None or isinstance(timestamp, datetime.datetime)
        assert FleetManagerRideStatus.contains(status)

        self.wb_id = long(wb_id)
        self.status = status
        self.taxi_id = int(taxi_id) if taxi_id else None
        self.lat = float(lat) if lat else None
        self.lon = float(lon) if lon else None
        self.timestamp = timestamp
        self.raw_status = raw_status

    def __str__(self):
        s = "%s %s" % (self.wb_id, FleetManagerRideStatus.get_name(self.status))
        if self.raw_status:
            s += " [%s]" % self.raw_status
        if self.taxi_id:
            s += ": assigned to taxi %s" % self.taxi_id
        if self.lat and self.lon:
            s += " located at %s,%s" % (self.lat, self.lon)
        if self.timestamp:
            s += " [%s]" % self.timestamp
        return s


class FleetManager(BaseModel):
    name = models.CharField(max_length=50)
    backend_path = models.CharField(max_length=50, blank=True, null=True) # e.g., fleet.backends.isr.ISR

    backend = None
    def __init__(self, *args, **kwargs):
        """Constructor.
        Sets the backend class as defined by the backend path.
        """
        super(FleetManager, self).__init__(*args, **kwargs)

        i = self.backend_path.rfind('.')
        module, attr = self.backend_path[:i], self.backend_path[i + 1:]

        mod = import_module(module)
        self.backend = getattr(mod, attr)

    def __unicode__(self):
        return self.name