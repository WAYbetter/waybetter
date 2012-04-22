import datetime
from common.models import BaseModel
from django.core.exceptions import ValidationError
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

ONGOING_STATUS_LIST = [FleetManagerRideStatus.ASSIGNED_TO_TAXI,
                       FleetManagerRideStatus.DRIVER_ACCEPTED,
                       FleetManagerRideStatus.WAITING_FOR_PASSENGER,
                       FleetManagerRideStatus.PASSENGER_PICKUP,
                       FleetManagerRideStatus.PASSENGER_DROPOFF]

class FleetManagerRide(object):
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
        assert FleetManagerRideStatus.contains(status)

        self.id = long(id)
        self.status = status
        self.taxi_id = long(taxi_id) if taxi_id else None
        self.lat = float(lat) if lat else None
        self.lon = float(lon) if lon else None
        self.timestamp = timestamp
        self.raw_status = raw_status

    def __str__(self):
        s = "%s %s" % (self.id, FleetManagerRideStatus.get_name(self.status))
        if self.raw_status:
            s += " [%s]" % self.raw_status
        if self.taxi_id:
            s += ": assigned to taxi %s" % self.taxi_id
        if self.lat and self.lon:
            s += " located at %s,%s" % (self.lat, self.lon)
        if self.timestamp:
            s += " [%s]" % self.timestamp
        return s

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

    @classmethod
    def get_ongoing_rides(cls):
        """Query the fleet manager for all rides with status in C{ONGOING_STATUS_LIST}.
        @return: A list of C{FleetManagerRide}.
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

    def get_ongoing_rides(self):
        return self.backend.get_ongoing_rides()