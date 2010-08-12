from google.appengine.api import memcache
from django.core.serializers import serialize
from django.utils.datetime_safe import datetime

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
    key = get_assignment_key(order_assignment.work_station)
    assignments = memcache.get(key) or []
    assignments.append(order_assignment)
    if not memcache.replace(key, assignments): # will fail if another process removed existing orders
        memcache.set(key, [order_assignment])

def set_heartbeat(workstation):
    key = get_heartbeat_key(workstation)
    memcache.set(key, datetime.now())
    
def get_orders(work_station):
    result = "[]"
    key = get_assignment_key(work_station)
    assignments = memcache.get(key) or []
    result = serialize("json", assignments)
    memcache.delete(key)

    return result


    