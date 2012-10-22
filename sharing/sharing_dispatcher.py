import traceback
from google.appengine.ext import deferred
from common.tz_support import default_tz_now
from common.util import notify_by_email
from django.utils import translation
from django.utils.translation import ugettext as _
from google.appengine.api.taskqueue import taskqueue
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from ordering.enums import RideStatus
from ordering.models import WorkStation, PENDING, ASSIGNED, SharedRide
from datetime import timedelta
from ordering.util import send_msg_to_passenger
from sharing.passenger_controller import send_ride_notifications
from sharing.station_controller import send_ride_voucher
from fleet import fleet_manager
import logging

MSG_DELIVERY_GRACE = 10 # seconds
NOTIFY_STATION_DELTA = timedelta(minutes=10)
DISPATCHING_TIME = 5 #minutes

def dispatching_cron(request):
    logging.info("cron: dispatch rides")

    rides_to_dispatch = SharedRide.objects.filter(status=RideStatus.PENDING, depart_time__lte=default_tz_now() + timedelta(minutes=DISPATCHING_TIME))
    for ride in rides_to_dispatch:
        deferred.defer(dispatch_ride, ride)

    return HttpResponse("OK")


def dispatch_ride(ride):
    logging.info("dispatch ride [%s]" % ride.id)

    if not ride.change_status(old_status=RideStatus.PENDING, new_status=RideStatus.PROCESSING):
        logging.warning("Ride dispatched twice: %s" % ride.id)
        return # nothing to do.

    work_station = assign_ride(ride)
    if work_station:
        q = taskqueue.Queue('ride-notifications')
        task = taskqueue.Task(url=reverse(send_ride_voucher), params={"ride_id": ride.id})
        q.add(task)

        if ride.dn_fleet_manager_id:
            deferred.defer(fleet_manager.create_ride, ride)
        else:
            logging.info("ride %s has no fleet manager" % ride.id)

        send_ride_notifications(ride)
        if not work_station.is_online:
            notify_by_email(u"Ride [%s] dispatched to offline workstation %s" % (ride.id, work_station), msg=ride.get_log())

    else:
        #TODO_WB: how do we handle this? cancel the orders?
        ride.change_status(old_status=RideStatus.PROCESSING, new_status=RideStatus.PENDING)
        notify_dispatching_failed(ride)


def assign_ride(ride):
    work_station = choose_workstation(ride)

    if work_station:
        try:
            station = work_station.station
            ride.station = station
            ride.dn_fleet_manager_id = station.fleet_manager_id
            if ride.change_status(old_status=RideStatus.PROCESSING, new_status=RideStatus.ASSIGNED): # calls save()
                return work_station

        except Exception:
            notify_by_email(u"Cannot assign ride [%s]" % ride.id, msg="%s\n%s" % (ride.get_log(), traceback.format_exc()))

    return None


def choose_workstation(ride):
    ws_list = WorkStation.objects.filter(accept_shared_rides=True)

    if ride.debug:
        ws_list = ws_list.filter(accept_debug=True)

    if ws_list:
        return ws_list[0]

    else:
        logging.error(u"No sharing stations found %s" % ride.get_log())
        return None


def notify_dispatching_failed(ride):
    current_lang = translation.get_language()
    for order in ride.orders.all():
        translation.activate(order.language_code)
        msg = _("We are sorry, but order #%s could not be completed") % order.id
        send_msg_to_passenger(order.passenger, msg)

    translation.activate(current_lang)

    notify_by_email(u"Ride [%s] Dispatching failed" % ride.id, msg=ride.get_log())