# -*- coding: utf-8 -*-

import logging
from google.appengine.ext.deferred import deferred
from common.decorators import receive_signal
from common.geo_calculations import distance_between_points
from common.langsupport.util import translate_to_lang
from common.signals import AsyncSignal
from common.util import  Enum
from django.core.urlresolvers import reverse
from django.utils.translation import gettext_noop as _
from fleet.models import FleetManagerRideStatus
from django.conf import settings

RIDE_TEXT_THRESHOLD = 0.5 # KM

class SignalType(Enum):
    TAXIRIDE_POSITION_CHANGED   = 1
    RIDE_STATUS_CHANGED         = 2

positions_update_signal = AsyncSignal(SignalType.TAXIRIDE_POSITION_CHANGED, providing_args=["positions"])
fmr_update_signal = AsyncSignal(SignalType.RIDE_STATUS_CHANGED, providing_args=["fmr"])

@receive_signal(fmr_update_signal)
def handle_assign_to_taxi(sender, signal_type, **kwargs):
    from ordering.models import BaseRide, PickMeAppRide, SharedRide, RideStatus

    fmr = kwargs["fmr"]
    ride = BaseRide.by_uuid(fmr.id)

    logging.info(u"fleet update received: %s" % fmr)
    if fmr.taxi_id and str(fmr.taxi_id) != ride.taxi_number:
        logging.info("taxi number changed: %s -> %s" % (ride.taxi_number, fmr.taxi_id))
        ride.update(taxi_number=fmr.taxi_id)
        if isinstance(ride, PickMeAppRide): # PickmeAppRide: send via SMS
            deferred.defer(do_notify_passenger, ride.order, _countdown=40) # wait 40 seconds and then notify passengers

    if isinstance(ride, SharedRide):
        accepted_statuses = [FleetManagerRideStatus.DRIVER_ACCEPTED, FleetManagerRideStatus.ASSIGNED_TO_TAXI, FleetManagerRideStatus.WAITING_FOR_PASSENGER,
                    FleetManagerRideStatus.PASSENGER_PICKUP, FleetManagerRideStatus.PASSENGER_DROPOFF]

        if fmr.taxi_id and fmr.status in accepted_statuses and ride.status == RideStatus.VIEWED:
            ride.change_status(old_status=RideStatus.VIEWED, new_status=RideStatus.ACCEPTED)


@receive_signal(positions_update_signal)
def send_ride_texts(sender, signal_type, positions, **kwargs):
    from ordering.models import SharedRide, RideStatus
    from fleet.fleet_manager import  send_ride_point_text

    for position in positions:
        ride = SharedRide.by_uuid(position.ride_uuid)
        if ride and ride.status == RideStatus.ACCEPTED:
            active_points = ride.points.filter(dispatched=False).order_by("stop_time")
            if active_points:
                current_point = active_points[0]
                next_point = active_points[1] if len(active_points) > 1 else None

                if distance_between_points(position.lat, position.lon, current_point.lat, current_point.lon) < RIDE_TEXT_THRESHOLD:
                    current_point.update(dispatched=True)
                    send_ride_point_text(ride, current_point, next_point=next_point)

def do_notify_passenger(order):
    from ordering.util import send_msg_to_passenger

    def _notify_order_passenger(order):
        logging.info("Ride status update: notifying passenger about taxi location for order: %s" % order)
        msg = translate_to_lang(_("To view your taxi: "), order.language_code)
        url = " http://%s%s" % (settings.DEFAULT_DOMAIN,
                               reverse("ordering.passenger_controller.track_order", kwargs={"order_id": order.id}))
        msg += url
        send_msg_to_passenger(order.passenger, msg)

    if order:
        ride = order.ride
        if ride:
            for o in ride.orders.all(): _notify_order_passenger(o)
        else:
            _notify_order_passenger(order)