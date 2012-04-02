import logging
from common.tz_support import to_task_name_safe
from ordering.models import RideComputation
from sharing.algo_api import submit_computations

def get_hotspot_computation_key(hotspot, hotspot_direction, hotspot_datetime):
    """

    @param hotspot_direction: "from" if the ride starts at hotspot, otherwise "to"
    @param hotspot_datetime: the time and date of the ride
    @return: unique key representing the hotspot at given time and direction. Should match task name expression "^[a-zA-Z0-9_-]{1,500}$"
    """
    return "_".join([str(hotspot.id), hotspot_direction, to_task_name_safe(hotspot_datetime)])

def get_hotspot_computation(hotspot, hotspot_type, depart_datetime, is_debug=False):
    """

    @param hotspot:
    @param hotspot_type: StopType.PICKUP or StopType.DROPOFF
    @param depart_datetime:
    @param is_debug:
    @return:
    """
    key = get_hotspot_computation_key(hotspot, hotspot_type, depart_datetime)
    if is_debug:
        key = "__DEBUG__%s" % key

    try:
        computation = RideComputation.objects.get(key=key)
    except RideComputation.DoesNotExist:
        computation = RideComputation(key=key, debug=is_debug)
        computation.hotspot_type = hotspot_type

        computation.save()
        logging.info("new computation created: id=%s key=%s" % (computation.id, key))
    except RideComputation.MultipleObjectsReturned:
        computation = RideComputation.objects.filter(key=key)[0]

    submit_time = depart_datetime - hotspot.order_processing_time
    submit_computations(computation.key, submit_time)

    return computation