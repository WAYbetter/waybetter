from google.appengine.ext import deferred
from django.conf import settings
from common.tz_support import default_tz_now, normalize_naive_israel_dt
from common.decorators import catch_view_exceptions
from common.util import safe_fetch, ga_track_event, first
from dateutil import parser as dateutil_parser
from django.http import HttpResponse
from django.utils import simplejson
from django.views.decorators.csrf import csrf_exempt
from fleet import fleet_manager
from fleet.models import AbstractFleetManagerBackend, FleetManagerRide, FleetManager, TaxiRidePosition
from fleet.backends.isr import DEFAULT_TIMEDELTA, WAYBETTER_STATUS_MAP, INITIAL_STATUS
from ordering.models import Station
from google.appengine.api.urlfetch import POST
from google.appengine.api import memcache
import datetime
import logging

WB_DEV_OPERATOR_ID = "8"

class ISRProxy(AbstractFleetManagerBackend):
    NAMESPACE = "fleet_backend_isrproxy"
    USERNAME = "***REMOVED***"
    PASSWORD = "***REMOVED***"
    base_url = "***REMOVED***"

    @classmethod
    def create_ride(cls, ride, station, taxi_number=None):
        fmr = None

        reply = None
        for retry in range(3):
            last_try = (retry == 2)
            reply = cls._fetch("CreateRide.aspx", {'ride': cls._create_ride(ride, station.fleet_station_id, taxi_number=taxi_number)}, notify=last_try)

            if reply:
                break

        if reply:
            fmr = cls._create_fmr_from_reply(reply)
            ga_track_event(None, "isr", "create_ride_success", ride.id)
        else:
            ga_track_event(None, "isr", "create_ride_failure", ride.id)

        return fmr

    @classmethod
    def cancel_ride(cls, ride_id):
        reply = cls._fetch("CancelRide.aspx", {'ride_id': ride_id})
        return bool(reply)

    @classmethod
    def get_ride(cls, ride_id):
        fmr = None

        reply = cls._fetch("GetRide.aspx", {'ride_id': ride_id})
        if reply:
            fmr = cls._create_fmr_from_reply(reply)

        return fmr

    @classmethod
    def is_ok(cls):
        ok = False
        url = "%s%s" % (cls.base_url, "Status.aspx")
        result = safe_fetch(url, deadline=30, notify=False)
        if result and result.content:
            status = simplejson.loads(result.content)
            if status.get('Status') == "OK":
                ok = True

        return ok

    @classmethod
    def send_message(cls, message, station_id, taxi_number, mirror=True):
        # mirror all text messages to our own taxi
        if mirror:
            cls.send_message(message, 8, 123, mirror=False)

        def _flip_hebrew(text):
            def is_hebrew(text):
                return any(u"\u0590" <= c <= u"\u05EA" for c in text)

            lines = text.split("\n")
            fixed_lines = []
            for line in lines:
                words = line.split(" ")
                fixed_words = []
                for word in words:
                    if is_hebrew(word):
                        fixed_words.append(word[::-1])
                    else:
                        fixed_words.append(word)
                fixed_lines.append(" ".join(fixed_words[::-1]))

            return "\n".join(fixed_lines)

        fixed_message = _flip_hebrew(message)
        logging.info(u"send text: '%s'" % fixed_message)
        reply = cls._fetch("SendText.aspx", {'message': fixed_message, "OP_ID": str(station_id), "Vehicle_ID": str(taxi_number) })
        logging.info(u"reply = %s" % reply)
        return bool(reply)

    @classmethod
    def set_taxi_assignment(cls, taxi_number, station_id, ride_uuid):
        key = cls._get_key_for_taxi_and_station(taxi_number, station_id)
        memcache.set(key, ride_uuid ,namespace=cls.NAMESPACE)
        logging.info("taxi assignment was set: %s -> %s (station=%s)" % (taxi_number, ride_uuid, station_id))

    @classmethod
    def get_taxi_assignment(cls, taxi_number, station_id):
        """
        returns the uuid for the ride the taxi is assigned to
        """
        logging.info("isr_proxy get assignment for taxi #%s (station %s)" % (taxi_number, station_id))

        if not taxi_number:
            return None

        key = cls._get_key_for_taxi_and_station(taxi_number, station_id)
        ride_uuid = memcache.get(key, namespace=cls.NAMESPACE)
        if not ride_uuid:  # try from db (maybe memcache was flushed)
            try:
                station = Station.objects.get(fleet_station_id=station_id)

                isrproxy_fm = first(lambda fm: fm.backend == ISRProxy, FleetManager.objects.all())
                isrproxy_ongoing_rides = fleet_manager.get_ongoing_rides(backend=isrproxy_fm)

                ride = first(lambda r: r.taxi_number == taxi_number and r.station == station, isrproxy_ongoing_rides)
                if ride:
                    ride_uuid = ride.uuid
                else:
                    logging.warning(u"no ongoing ride found for station %s and taxi %s" % (station, taxi_number))

            except Station.DoesNotExist, e:
                logging.error("station with fleet id %s not found" % station_id)

            except IndexError, e:
                logging.error("isr_proxy fleet manager does not exist in db")

        logging.info("taxi assigned to ride: %s" % ride_uuid)
        return ride_uuid

    @classmethod
    def _get_key_for_taxi_and_station(cls, taxi_number, station_id):
        return "%s_%s" % (taxi_number, station_id)

    @classmethod
    def _resolve_status(cls, raw_status):
        try:
            return WAYBETTER_STATUS_MAP[raw_status]
        except KeyError, e:
            logging.error("isrproxy: cannot resolve status %s" % raw_status)
            return None

    @classmethod
    def _fetch(cls, action, data, method=POST, notify=True):
        url = "%s%s" % (cls.base_url, action)
        data.update({
            'username': cls.USERNAME,
            'password': cls.PASSWORD
        })
        data = simplejson.dumps(data)

        logging.info("isrproxy %s: data=%s" % (action, data))
        reply = safe_fetch(url, payload=data, method=method, deadline=30, notify=notify)
        if reply and reply.content:
            logging.info("_fetch result: %s" % reply.content)
            result = simplejson.loads(reply.content)
            if result.get("success", False):
                return reply
            else:
                logging.error("isr_proxy %s failed: %s" % (action, result.get("error")))
                return None

        return None


    @classmethod
    def _create_fmr_from_reply(cls, reply):
        data = simplejson.loads(reply.content)
        ride_data = data.get("ride")
        return cls._create_fmr(ride_data)

    @classmethod
    def _create_fmr(cls, ride_data):
        if not ride_data:
            return None

        ride_uuid = ride_data.get("External_Order_ID")
        raw_status = ride_data.get("Status")
        status = cls._resolve_status(raw_status)
        taxi_number = ride_data.get("Operating_Vehicle")
        lat = ride_data.get("Lat")
        lon = ride_data.get("Lon")
        timestamp = ride_data.get("Timestamp")
        station_id = ride_data.get("Operator_ID")

        if ride_uuid and taxi_number and station_id:  # assign taxi to ride on status updates
            cls.set_taxi_assignment(taxi_number, station_id, ride_uuid)

        if not ride_uuid:  # populate ride_uuid for position updates
            ride_uuid = cls.get_taxi_assignment(taxi_number, station_id)

        if timestamp:
            timestamp = dateutil_parser.parse(timestamp)
            timestamp = normalize_naive_israel_dt(timestamp)

        return FleetManagerRide(ride_uuid, status, taxi_number, station_id, lat, lon, timestamp, raw_status=raw_status)

    @classmethod
    def _create_ride(cls, ride, isr_station_id, taxi_number=None):
        from ordering.models import PickMeAppRide, SharedRide
        from fleet.isr_tests import FakeSharedRide

        # ISRsays: these fields are required but not reflected in ISR client UI
        start_time = default_tz_now() + DEFAULT_TIMEDELTA
        finish_time = start_time + DEFAULT_TIMEDELTA

        order = None
        if isinstance(ride, PickMeAppRide):
            order = ride.order
        elif isinstance(ride, SharedRide):
            order = ride.first_pickup.pickup_orders.all()[0]
        elif isinstance(ride, FakeSharedRide):
            order = ride.orders.all()[0]

        stop_number = 0 # TODO_WB: the pickup order, change when ISR supports more than 1 stop
        first_stop = cls._create_order_stop(order, stop_number)  #TODO_WB: get from ride
        return {
            'Auto_Order': False,
            'Comments': order.comments,
            'Remarks': '',
            'Visa_ID': 'visa_id',
            'Customer': cls._create_customer_data(order.passenger),
            'External_Order_ID': ride.uuid,
            'Preferred_Operator_ID': int(isr_station_id),
            'Preferred_Vehicle_ID': taxi_number if taxi_number else '',
            # ex_order.Prefered_Vehicle_ID = -1,
            # TODO_WB: if passenger.business the business is contact?
            'Contact_Name': '',
            'Contact_Phone': '',
            'Start_Time': (order.depart_time or start_time).isoformat(),
            'Finish_Time': (order.arrive_time or finish_time).isoformat(),
            'Stops': [first_stop],
            'Order_Type': 'Taxi_Order',
            'Status': INITIAL_STATUS
        }

    @classmethod
    def _create_customer_data(cls, passenger):
        # TODO_WB: if passenger.business the business is customer?
        return {
            'Cell_phone': passenger.phone,
            'Phone': passenger.phone,
            'Name': passenger.full_name
        }

    @classmethod
    def _create_order_stop(cls, order, stop_number):
        return {
            'Address': cls._create_stop_address(order),
            'Passengers': [cls._create_passenger(order.passenger)],
            'Stop_Order': stop_number,

            # this field is used as the start time in ISR client UI
            'Stop_Time': (order.depart_time or (default_tz_now() + DEFAULT_TIMEDELTA)).isoformat()
        }


    @classmethod
    def _create_stop_address(cls, order, type="from"):
        city = getattr(order, "%s_city" % type)
        return {
            'Address_Type': 'Unknown',
            'Full_Address': getattr(order, "%s_raw" % type),
            'City': city.name if city else "",
            'Street': getattr(order, "%s_street_address" % type),
            'House': str(getattr(order, "%s_house_number" % type) or ""),
            'Lat': getattr(order, "%s_lat" % type),
            'Lon': getattr(order, "%s_lon" % type)
            # 'Poi': ""

        }

    @classmethod
    def _create_passenger(cls, passenger):
        p = {
            'Phone': passenger.phone,
            'First_Name': passenger.full_name,
            'Last_Name': "",
            'Passenger_External_ID': passenger.id
        }
        return p


# TODO_WB: check that requests originate from our proxy request.META.get("HTTP_HOST") ==
@csrf_exempt
@catch_view_exceptions
def update_status(request):
    """ View for calls by ISRProxy backend on ride status updates. """
    raw_data = request.raw_post_data
    logging.info("isrproxy update_status: %s" % raw_data)

    update_status_data = simplejson.loads(raw_data)

    # redirect update to dev server in production environment
    if update_status_data.get('Operator_ID') == WB_DEV_OPERATOR_ID and not settings.DEV:
        deferred.defer(safe_fetch, url="http://dev.latest.waybetter-app.appspot.com/fleet/isrproxy/update/status/", payload=raw_data, method=POST, notify=False)
        return HttpResponse("OK")

    fmr = ISRProxy._create_fmr(update_status_data)
    fleet_manager.update_ride(fmr)

    mcns = "ga_isrproxy_ride_updates"
    getkey = lambda fmr: str(fmr.id)

    now = datetime.datetime.now()
    last_update_dt = memcache.get(getkey(fmr), namespace=mcns)
    val = (now - last_update_dt).seconds if last_update_dt else 0
    memcache.set(getkey(fmr), now, namespace=mcns)

   # Log status position as a position update
    if fmr.lat and fmr.lon:
        taxi_position = TaxiRidePosition(fmr.station_id, fmr.taxi_id, fmr.id, fmr.lat, fmr.lon, fmr.timestamp)
        fleet_manager.update_positions([taxi_position])
    else:
        logging.warning("ride update with no location info received: %s" % fmr.serialize())

    ga_track_event(request, "isr", "update_ride", fmr.id)
    ga_track_event(request, "isr", fmr.raw_status, fmr.id, val)

    return HttpResponse("OK")



@csrf_exempt
@catch_view_exceptions
def update_positions(request):
    """ View for calls by ISRProxy backend on taxi positions updates. """
    raw_data = request.raw_post_data
    logging.info("isrproxy update_positions: %s" % raw_data)
    update_positions_data = simplejson.loads(raw_data)

    # redirect update to dev server in production environment
    if not settings.DEV:
        dev_positions = filter(lambda p: p.get("Operator_ID") == WB_DEV_OPERATOR_ID, update_positions_data)
        if dev_positions:
            deferred.defer(safe_fetch, url="http://dev.latest.waybetter-app.appspot.com/fleet/isrproxy/update/positions/", payload=simplejson.dumps(dev_positions), method=POST, notify=False)
            update_positions_data = filter(lambda p: p.get("Operator_ID") != WB_DEV_OPERATOR_ID, update_positions_data)


    ride_positions = []
    for rp_data in update_positions_data:
        station_id = rp_data.get("Operator_ID")
        taxi_id = rp_data.get("Vehicle_ID")
        lat = rp_data.get("Lat")
        lon = rp_data.get("Lon")
        timestamp = rp_data.get("Timestamp")

        ride_uuid = ISRProxy.get_taxi_assignment(taxi_id, station_id)

        if all([station_id, ride_uuid, taxi_id, lat, lon, timestamp]):
            timestamp = dateutil_parser.parse(timestamp)
            timestamp = normalize_naive_israel_dt(timestamp)
            ride_positions.append(TaxiRidePosition(station_id, taxi_id, ride_uuid, lat, lon, timestamp))

    fleet_manager.update_positions(ride_positions)
    return HttpResponse("OK")
