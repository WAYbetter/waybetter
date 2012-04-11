import datetime
from common.models import BaseModel
from django.db import models
from django.utils.importlib import import_module
from common.util import Enum

class FleetManagerOrderStatus(Enum):
    PENDING = 0
    ASSIGNED_TO_TAXI = 1
    DRIVER_ACCEPTED = 2
    WAITING_FOR_PASSENGER = 3
    PASSENGER_PICKUP = 4
    PASSENGER_DROPOFF = 5
    PASSENGER_NO_SHOW = 6
    COMPLETED = 7
    CANCELLED = 8


class AbstractFleetManager(object):
    @classmethod
    def create_order(cls, order, station_id):
        """Create an order on the fleet manager servers.
        @param order: an C{ordering.Order} instance.
        @param station_id: id of the station which will receive the order.
        @return: a C{FleetManagerOrder} instance, or None if creation failed.
        """
        raise NotImplementedError()

    @classmethod
    def cancel_order(cls, order_id):
        """Delete an order from the fleet manager servers.
        @param order_id: the id of the order to delete.
        @return: True/False on success/fail.
        """
        raise NotImplementedError()

    @classmethod
    def get_order(cls, order_id):
        """Query the fleet manager for an order.
        @param order_id: the id of the order to query
        @return: C{FleetManagerOrder} or None
        """
        raise NotImplementedError()


class FleetManagerOrder(object):
    def __init__(self, wb_id, status, taxi_id, lat, lon, timestamp, raw_status=None):
        """Constructor.

        @param wb_id: Long representing the id of the order as recorded in our db.
        @param status: the status as one of C{FleetManagerOrderStatus}.
        @param taxi_id: Number of the taxi assigned to this order or None.
        @param lat: latitude of the taxi captured on C{timestamp} or None.
        @param lon: longitude of the taxi captured on C{timestamp} or None.
        @param timestamp: A datetime.datetime instance or None
        """
        assert wb_id
        assert timestamp is None or isinstance(timestamp, datetime.datetime)

        self.wb_id = long(wb_id)
        self.status = status
        self.taxi_id = taxi_id
        self.lat = lat
        self.lon = lon
        self.timestamp = timestamp
        self.raw_status = raw_status

    def __str__(self):
        s = "%s %s" % (self.wb_id, FleetManagerOrderStatus.get_name(self.status))
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
    backend_path = models.CharField(max_length=50, default="fleet.backends.default.DefaultFleetManager")

    def __init__(self, *args, **kwargs):
        super(FleetManager, self).__init__(*args, **kwargs)

        i = self.backend_path.rfind('.')
        module, attr = self.backend_path[:i], self.backend_path[i + 1:]

        mod = import_module(module)
        self.backend = getattr(mod, attr)

    def __unicode__(self):
        return self.name