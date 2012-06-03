from google.appengine.ext import deferred
from common.tz_support import utc_now
from common.util import notify_by_email
from django.utils import translation
from django.utils.translation import ugettext as _
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from google.appengine.api.taskqueue import taskqueue
from common.decorators import internal_task_on_queue, catch_view_exceptions
from django.core.urlresolvers import reverse
from ordering import station_connection_manager
from ordering.models import WorkStation, PENDING, ASSIGNED, SharedRide
from datetime import timedelta
from ordering.util import send_msg_to_passenger
from sharing.passenger_controller import send_ride_notifications
from sharing.station_controller import send_ride_voucher
from fleet import fleet_manager
import logging

MSG_DELIVERY_GRACE = 10 # seconds
NOTIFY_STATION_DELTA = timedelta(minutes=10)

def dispatch_ride(ride):
    work_station = assign_ride(ride)
    if work_station:
#        station_connection_manager.push_ride(work_station, ride)
#        task = taskqueue.Task(url=reverse(push_ride_task), countdown=MSG_DELIVERY_GRACE, params={"ride_id": ride.id, "ws_id": work_station.id})
#        taskqueue.Queue('orders').add(task)
        
        q = taskqueue.Queue('ride-notifications')
        task = taskqueue.Task(url=reverse(send_ride_voucher), params={"ride_id": ride.id})
        q.add(task)


# TODO_WB:  uncomment #1 and remove #2 when merging with stable
        #1
#        if ride.dn_fleet_manager_id:
#            fleet_manager.create_ride(ride)
#        else:
#            logging.info("ride %s has no fleet manager" % ride.id)
        #2
        try:
            from google.appengine.api.urlfetch import fetch
            fetch("http://devisr.latest.waybetter-app.appspot.com/fleet/create/ride/%s/" % ride.id)
        except Exception, e:
            logging.error(e)

        send_ride_notifications(ride)
        if not work_station.is_online:
            notify_by_email(u"Ride [%s] dispatched to offline workstation %s" % (ride.id, work_station), msg=ride.get_log())

    else:
        #TODO_WB: how do we handle this? cancel the orders?
        notify_dispatching_failed(ride)


def assign_ride(ride):
    work_station = choose_workstation(ride)

    if work_station:
        try:
            station = work_station.station
            ride.station = station
            ride.dn_fleet_manager_id = station.fleet_manager_id
            ride.change_status(old_status=PENDING, new_status=ASSIGNED) # calls save()
            return work_station

        except Exception:
            notify_by_email(u"UpdateStatusError: Cannot assign ride [%s]" % ride.id, msg=ride.get_log())

    return None


def choose_workstation(ride):
    confining_stations = [order.confining_station for order in ride.orders.all()]
    confining_station = confining_stations[0] if confining_stations and all(map(lambda s: s==confining_stations[0], confining_stations)) else None

    log = u"Choose Workstation:\nconfining_stations=[%s]\n%s" % (",".join([unicode(s) for s in confining_stations]), ride.get_log())

    logging.info(log)

    if confining_station:
        ws_list = WorkStation.objects.filter(station=confining_station, accept_shared_rides=True)
    else:
        ws_list = WorkStation.objects.filter(accept_shared_rides=True)

    if ride.debug:
        ws_list = ws_list.filter(accept_debug=True)

    if ws_list:
        return ws_list[0]

    else:
        logging.error(u"No sharing stations found %s" % log)
        return None


@csrf_exempt
@catch_view_exceptions
@internal_task_on_queue("orders")
def push_ride_task(request):
    ride_id = request.POST.get("ride_id")
    ws_id = request.POST.get("ws_id")
    try:
        ride = SharedRide.by_id(id=ride_id, safe=False)
        work_station = WorkStation.by_id(ws_id, safe=False)
        if not ride.received_time:
            if utc_now() < ride.depart_time - NOTIFY_STATION_DELTA:
                logging.info(u"push ride task: ride=%s, workstation=%s" % (ride_id, work_station))
                station_connection_manager.push_ride(work_station, ride)

                task = taskqueue.Task(url=reverse(push_ride_task), countdown=MSG_DELIVERY_GRACE, params={"ride_id": ride_id, "ws_id": ws_id})
                taskqueue.Queue('orders').add(task)
            elif not ride.debug:
                msg = u"work station: %s\n%s" % (work_station, ride.get_log())
                notify_by_email(u"Ride [%s]: Not delivered to station %s" % (ride.id, ride.station.name), msg=msg)

    except (SharedRide.DoesNotExist, WorkStation.DoesNotExist):
        logging.error(u"push ride task error (model.DoesNotExist): ride_id=%s, ws_id=%s" % (ride_id, ws_id))

    return HttpResponse("OK")


def notify_dispatching_failed(ride):
    current_lang = translation.get_language()
    for order in ride.orders.all():
        translation.activate(order.language_code)
        msg = _("We are sorry, but order #%s could not be completed") % order.id
        send_msg_to_passenger(order.passenger, msg)

    translation.activate(current_lang)

    notify_by_email(u"Ride [%s] Dispatching failed" % ride.id, msg=ride.get_log())