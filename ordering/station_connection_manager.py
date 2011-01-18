from google.appengine.api import memcache
from django.core.serializers import serialize
from django.utils.datetime_safe import datetime
from ordering.models import OrderAssignment

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
    json = OrderAssignment.serialize_for_workstation(order_assignment)
#    json = serialize("json", [order_assignment.order])
    key = get_assignment_key(order_assignment.work_station)
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


    