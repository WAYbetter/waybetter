import logging
from google.appengine.api.channel.channel import InvalidChannelClientIdError
from common.tz_support import utc_now
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from google.appengine.api import channel
from analytics.models import AnalyticsEvent
from common.decorators import  internal_task_on_queue, catch_view_exceptions
from common.util import  EventType, notify_by_email, get_current_version
from django.utils import simplejson
from datetime import timedelta
from ordering.models import OrderAssignment, PENDING, WorkStation
from common.langsupport.util import translate_to_ws_lang

ugettext =                      lambda s: s
DUMMY_ADDRESS =                 ugettext("This is a test order")
DUMMY_ID =                      "dummy"
CONNECTION_CHECK_KEY =          "check_connection"
CONNECTION_CHECK_INTERVAL =     5 * 60 # 5 minutes
IS_DEAD_DELTA =                 35
ALERT_DELTA =                   timedelta(minutes=30)

def is_workstation_available(work_station):
    return work_station.is_online

def check_connection(ws):
    orders = [{
        "key": CONNECTION_CHECK_KEY
    }]

    _do_push(ws, orders)

def push_order(order_assignment):
    """
    Retrieve the order and workstation from an assignment and add the order to the workstation's queue.
    """
    orders = OrderAssignment.serialize_for_workstation(order_assignment)
    _do_push(order_assignment.work_station, orders)

def push_dummy_order(ws):
    orders = [{"pk": DUMMY_ID,
             "status": PENDING,
             "from_raw": translate_to_ws_lang(DUMMY_ADDRESS, ws),
             "seconds_passed": "10"}]
    _do_push(ws, orders)


def _do_push(obj, data):
    json = simplejson.dumps(data)
    try:
        channel.send_message(obj.channel_id, json)
    except InvalidChannelClientIdError:
        logging.error("InvalidChannelClientIdError: could not sent message '%s' to obj: %s with channel id: '%s'" % (json, obj, obj.channel_id))

def workstation_connected(channel_id):
    _set_workstation_online_status(channel_id, True)

def workstation_disconnected(channel_id):
    _set_workstation_online_status(channel_id, False)

def _set_workstation_online_status(channel_id, status):
    workstation = None
    try:
        workstation = WorkStation.objects.get(channel_id=channel_id)
    except WorkStation.DoesNotExist:
        logging.warn("No workstation found for channel_id '%s'" % channel_id)

    if workstation:
        workstation.is_online = status
        if status:
            logging.info("Workstation connected: %d" % workstation.id)
        else:
            logging.info("Workstation disconnected: %d" % workstation.id)
            # clear channel_id field
            workstation.channel_id = None

        workstation.save()


@csrf_exempt
@catch_view_exceptions
@internal_task_on_queue("log-events")
def handle_dead_workstations(request):
    ws_id = request.POST.get("workstation_id")
    workstation = None
    try:
        workstation = WorkStation.objects.get(id=ws_id)
    except WorkStation.DoesNotExist:
        logging.error("handle_dead_workstations: invalid workstation_id '%s" % ws_id)

    if workstation:
        last_event = AnalyticsEvent.objects.filter(work_station=workstation, type__in=[EventType.WORKSTATION_UP, EventType.WORKSTATION_DOWN]).order_by('-create_date')[:1]
        if last_event:
            last_event = last_event[0]
            if last_event.type == EventType.WORKSTATION_DOWN and (utc_now() - last_event.create_date) >= ALERT_DELTA:
                # send station down mail
                msg = u"Workstation has been down for the last %d minutes:\n\tid = %d station = %s" % (ALERT_DELTA.seconds / 60, workstation.id, workstation.dn_station_name)
                notify_by_email(u"Workstation down", msg)

    return HttpResponse("OK")

def send_heartbeat(request):
    current_version = get_current_version()
    for ws in WorkStation.objects.filter(is_online=True):
        logging.info("sending heartbeat to: %s" % ws)
        _do_push(ws, {"heartbeat": current_version})

    return HttpResponse("OK")
