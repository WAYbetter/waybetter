import logging
from common.tz_support import to_task_name_safe
from common.util import notify_by_email
from ordering.models import RideComputation, StopType, OrderType, RideComputationStatus
from sharing.algo_api import submit_computations

def get_hotspot_computation_key(hotspot, hotspot_type, hotspot_datetime):
    """

    @param hotspot_type: StopType.PICKUP or StopType.DROPOFF
    @param hotspot_datetime: the time and date of the ride
    @return: unique key representing the hotspot at given time and direction. Should match task name expression "^[a-zA-Z0-9_-]{1,500}$"
    """
    return "_".join([str(hotspot.id), StopType.get_name(hotspot_type), to_task_name_safe(hotspot_datetime)])


def get_hotspot_computation(order):
    """
    Get a RideComputation in which the given order will be included when submitting to the sharing algorithm.
    The order is assumed to have a .hotspot, .hotspot_type, .depart_time and .arrive_time fields.
    These fields determine a key by which the returned RideComputation is computed.

    @param order: An C{Order} having hotspot, hotspot_type, depart_time and arrive_time fields.
    @return: A C{RideComputation}.
    """
    hotspot = order.hotspot
    hotspot_type = order.hotspot_type
    depart_datetime = order.depart_time
    arrive_datetime = order.arrive_time

    submit_datetime = depart_datetime - hotspot.order_processing_time(OrderType.SHARED)

    if hotspot_type == StopType.PICKUP:
        hotspot_datetime = hotspot.get_next_interval(depart_datetime)
    else:
        hotspot_datetime = hotspot.get_next_interval(arrive_datetime)

    key = get_hotspot_computation_key(hotspot, hotspot_type, hotspot_datetime)
    if order.debug:
        key = "DEBUG__%s" % key

    def new_computation():
        kwargs = {
            'key': key,
            'hotspot_type': hotspot_type,
            'hotspot_datetime': hotspot_datetime,
            'submit_datetime': submit_datetime,
            'debug': order.debug
        }
        computation = RideComputation(**kwargs)
        computation.save()
        logging.info("new computation created: id=%s key=%s" % (computation.id, key))
        return computation


    submit = False
    computations = RideComputation.objects.filter(key=key)

    # This is the first order of its characteristics.
    # Create a new RideComputation and submit it.
    if not computations:
        computation = new_computation()
        submit = True

    # Previous orders of the same characteristics exist.
    # If there is a pending computation (has not submitted) its submit time is updated if necessary.
    else:
        try:
            computation = filter(lambda c: c.status == RideComputationStatus.PENDING, computations)[0]

            if submit_datetime < computation.submit_datetime:
                computation.submit_datetime = submit_datetime
                computation.save()
                logging.info("updated computation [%s] submit time -> %s" % (computation.id, submit_datetime.strftime("%H:%M")))
                submit = True

        # Existing computations has already been submitted. Create a new RideComputation and submit it.
        # This can happen when a short ride is booked after a long ride was booked and both are arriving at hotspot on the same hour.
        except IndexError:
            computation = new_computation()
            submit = True
            notify_by_email("Order Booked to already submitted interval", "\n".join([
                "This is not an error. Will created a new computation for the same interval.",
                "order id: %s" % order.id,
                "computation id: %s" % computation.id,
                "computation status: %s" % computation.get_status_display(),
                ]))

    if submit:
        submit_computations(computation.key, computation.submit_datetime)

    return computation