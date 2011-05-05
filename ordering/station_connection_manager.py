import logging
from google.appengine.api import memcache
from common.util import get_channel_key
from django.utils.datetime_safe import datetime
from django.utils import simplejson
from ordering.models import OrderAssignment, PENDING
from common.langsupport.util import translate_to_ws_lang

ugettext = lambda s: s
DUMMY_ADDRESS = ugettext("This is a test order")
DUMMY_ID = "dummy"
IS_DEAD_DELTA = 35

def get_heartbeat_key(work_station):
    return "heartbeat_for_ws.%d" % work_station.id

def get_assignment_key(work_station):
    return "assignments_for_ws.%d" % work_station.id


def is_workstation_available(work_station):
   
    heartbeat = memcache.get(get_heartbeat_key(work_station))
    if not heartbeat:
        return False

    return (datetime.now() - heartbeat).seconds < IS_DEAD_DELTA

def push_order(order_assignment):
    """
    Retrieve the order and workstation from an assignment and add the order to the workstation's queue.
    """
    json = OrderAssignment.serialize_for_workstation(order_assignment)
    _do_push_order(order_assignment.work_station, json)

def push_dummy_order(ws):
    json = simplejson.dumps([{"pk": DUMMY_ID,
                             "status": PENDING,
                             "from_raw": translate_to_ws_lang(DUMMY_ADDRESS, ws),
                             "seconds_passed": "10"}])
    _do_push_order(ws, json)

def _do_push_order(ws, json):
    key = get_assignment_key(ws)
    assignments = memcache.get(key) or []
    assignments.append(json)
    if not memcache.replace(key, assignments): # will fail if another process removed existing orders
        memcache.set(key, [json])

def set_heartbeat(workstation):
    key = get_heartbeat_key(workstation)
    memcache.set(key, datetime.now())
    
def get_orders(work_station):
    """
    takes (gets & deletes) from the Memecache the list of serialized OrderAssignmenets
    assigned to the given workstation.
    """
    key = get_assignment_key(work_station)
    result = memcache.get(key) or []
    memcache.delete(key)  # TODO_WB: risk of synchronization problem here!
    return result

    