import logging
from common.tz_support import to_task_name_safe
from ordering.models import RideComputation, StopType
from sharing.algo_api import submit_computations

def get_hotspot_computation_key(hotspot, hotspot_type, hotspot_datetime):
    """

    @param hotspot_type: StopType.PICKUP or StopType.DROPOFF
    @param hotspot_datetime: the time and date of the ride
    @return: unique key representing the hotspot at given time and direction. Should match task name expression "^[a-zA-Z0-9_-]{1,500}$"
    """
    return "_".join([str(hotspot.id), StopType.get_name(hotspot_type), to_task_name_safe(hotspot_datetime)])

def get_hotspot_computation(hotspot, hotspot_type, depart_datetime, arrive_datetime, is_debug=False):
    """

    @param hotspot_type: StopType.PICKUP or StopType.DROPOFF
    @return: RideComputation
    """
    if hotspot_type == StopType.PICKUP:
        hotspot_datetime = hotspot.get_next_active_datetime(depart_datetime)
    else:
        hotspot_datetime = hotspot.get_next_active_datetime(arrive_datetime)

    key = get_hotspot_computation_key(hotspot, hotspot_type, hotspot_datetime)
    if is_debug:
        key = "DEBUG__%s" % key

    submit_datetime = depart_datetime - hotspot.order_processing_time
    submit = False
    try:
        computation = RideComputation.objects.filter(key=key)[0]
        if submit_datetime < computation.submit_datetime:
            logging.info("updated computation [%s] submit time -> %s" % (computation.id, submit_datetime.strftime("%H:%M")))
            computation.submit_datetime = submit_datetime
            computation.save()
            submit = True
    except IndexError:
        kwargs = {
            'key': key,
            'hotspot_type': hotspot_type,
            'hotspot_datetime': hotspot_datetime,
            'submit_datetime': submit_datetime,
            'debug': is_debug
        }
        computation = RideComputation(**kwargs)
        computation.save()
        submit = True
        logging.info("new computation created: id=%s key=%s" % (computation.id, key))

    if submit:
        submit_computations(computation.key, computation.submit_datetime)

    return computation