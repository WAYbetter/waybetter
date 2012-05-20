import datetime
from common.models import BaseModel
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.importlib import import_module
from common.tz_support import to_js_date
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

class FleetManagerRide(object):
    """ An object representing a ride by a fleet manager backend. """
    def __init__(self, id, status, taxi_id, lat, lon, timestamp, raw_status=None):
        """Constructor.
        @param id: Long representing the id of the ride as recorded in our db.
        @param status: Number representing the status as one of C{FleetManagerRideStatus}.
        @param taxi_id: Number of the taxi assigned to this ride or None.
        @param lat: latitude of the taxi captured on C{timestamp} or None.
        @param lon: longitude of the taxi captured on C{timestamp} or None.
        @param timestamp: A datetime.datetime instance or None.
        @param raw_status: The original status as returned by the backend.
        """
        assert id
        assert timestamp is None or isinstance(timestamp, datetime.datetime)
        assert FleetManagerRideStatus.contains(status), "Unknown FleetManagerRideStatus: %s" % raw_status

        self.id = long(id)
        self.status = status
        self.taxi_id = long(taxi_id) if taxi_id else None
        self.lat = float(lat) if lat else None
        self.lon = float(lon) if lon else None
        self.timestamp = timestamp
        self.raw_status = raw_status

    def __str__(self):
        s = "%s: ride %s %s" % (self.timestamp, self.id, FleetManagerRideStatus.get_name(self.status))
        if self.raw_status:
            s += " [%s]" % self.raw_status
        if self.taxi_id:
            s += ": assigned to taxi %s" % self.taxi_id
        if self.lat and self.lon:
            s += " located at %s,%s" % (self.lat, self.lon)
        return s

    def serialize(self):
        d = {}
        for attr in ["id", "status", "taxi_id", "lat", "lon", "raw_status"]:
            d[attr] = getattr(self, attr)
        d["timestamp"] = to_js_date(self.timestamp)
        return d

class TaxiRidePosition(object):
    """ An object representing the position of a taxi assigned to a ride by a fleet manager backend """
    def __init__(self, station_id, taxi_id, ride_id, lat, lon, timestamp):
        """ Constructor.
        @param station_id: Number
        @param taxi_id: Number
        @param ride_id: Number
        @param lat: Float
        @param lon: Float
        @param timestamp: datetime.datetime
        """
        assert all([station_id, taxi_id, ride_id, lat, lon])
        assert timestamp is None or isinstance(timestamp, datetime.datetime)

        self.station_id = long(station_id)
        self.taxi_id = long(taxi_id)
        self.ride_id = long(ride_id)
        self.lat = float(lat)
        self.lon = float(lon)
        self.timestamp = timestamp

    def __str__(self):
        return "%s: ride %s taxi %s.%s at (%s,%s)" % (self.timestamp, self.ride_id, self.station_id, self.taxi_id, self.lat, self.lon)

    def serialize(self):
        d = {}
        for attr in ["station_id", "taxi_id", "ride_id", "lat", "lon"]:
            d[attr] = getattr(self, attr)
        d["timestamp"] = to_js_date(self.timestamp)
        return d


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


class FleetManager(BaseModel, AbstractFleetManagerBackend):
    name = models.CharField(max_length=50)
    backend_path = models.CharField(max_length=50) # e.g., fleet.backends.isr.ISR

    def clean(self):
        backend = None
        try:
            backend = self._get_backend()
        except Exception:
            pass

        if not backend:
            raise ValidationError("Invalid backend path")

    @property
    def backend(self):
        return self._get_backend()

    def _get_backend(self):
        i = self.backend_path.rfind('.')
        module, attr = self.backend_path[:i], self.backend_path[i + 1:]

        mod = import_module(module)
        return getattr(mod, attr)

    def __unicode__(self):
        return self.name

    def create_ride(self, ride, station):
        return self.backend.create_ride(ride, station)

    def cancel_ride(self, ride_id):
        return self.backend.cancel_ride(ride_id)

    def get_ride(self, ride_id):
        return self.backend.get_ride(ride_id)