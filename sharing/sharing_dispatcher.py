from google.appengine.ext import deferred
from common.tz_support import utc_now
from common.util import notify_by_email
from django.utils import translation
from django.utils.translation import ugettext as _
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from google.appengine.api.taskqueue import taskqueue
from common.decorators import receive_signal, internal_task_on_queue, catch_view_exceptions
from django.core.urlresolvers import reverse
from ordering import station_connection_manager
from ordering.errors import UpdateStatusError
from ordering.models import WorkStation, PENDING, ASSIGNED, SharedRide
from datetime import timedelta
from ordering.util import send_msg_to_passenger
from sharing.passenger_controller import send_ride_notifications
from sharing.station_controller import send_ride_voucher, mark_ride_not_taken_task
import signals
import logging

MSG_DELIVERY_GRACE = 10 # seconds
NOTIFY_STATION_DELTA = timedelta(minutes=10)

@receive_signal(signals.ride_created_signal)
def ride_created(sender, signal_type, obj, **kwargs):
    logging.info("ride_created_signal: %s" % obj)
    ride = obj
    dispatch_ride(ride)


def dispatch_ride(ride):
    work_station = assign_ride(ride)
    if work_station:
#        station_connection_manager.push_ride(work_station, ride)
#        task = taskqueue.Task(url=reverse(push_ride_task), countdown=MSG_DELIVERY_GRACE, params={"ride_id": ride.id, "ws_id": work_station.id})
#        taskqueue.Queue('orders').add(task)
        
        if work_station.station.vouchers_emails:
            q = taskqueue.Queue('ride-notifications')
            task = taskqueue.Task(url=reverse(send_ride_voucher), params={"ride_id": ride.id})
            q.add(task)

        send_ride_notifications(ride)
        deferred.defer(mark_ride_not_taken_task, ride_id=ride.id, _eta=ride.depart_time)

#    task = taskqueue.Task(url=reverse(mark_ride_not_taken_task), eta=ride.depart_time, params={"ride_id": ride.id})
#    q = taskqueue.Queue('orders')
#    q.add(task)
    else:
        #TODO_WB: how do we handle this? cancel the orders?
        notify_dispatching_failed(ride)


def assign_ride(ride):
    work_station = choose_workstation(ride)

    if work_station:
        try:
            ride.station = work_station.station

            # TODO_WB
            # in fax sending mode we assume all dispatched rides will be accepted
            ride.change_status(old_status=PENDING, new_status=ASSIGNED) # calls save()
#            ride.change_status(old_status=PENDING, new_status=ACCEPTED) # calls save()

#            if work_station.is_online:
#                notify_by_email(u"Ride [%s] assigned successfully to workstation %s" % (ride.id, work_station), msg=get_ride_log(ride))
#            else:
#                notify_by_email(u"Ride [%s] assigned to offline workstation %s" % (ride.id, work_station), msg=get_ride_log(ride))

            return work_station

        except UpdateStatusError:
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