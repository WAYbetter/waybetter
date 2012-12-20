from datetime import timedelta
import logging
import traceback
from google.appengine.ext import deferred
from common.models import Counter
from common.tz_support import default_tz_now_min, default_tz_now_max
from django.http import HttpResponse, HttpResponseBadRequest
from ordering.models import Order, OrderType, CHARGED, APPROVED

def calc_counters(request):
    start_date = None if request.GET.get("do_all") else (default_tz_now_min() - timedelta(days=1)) # all or start for yesterday
    end_date = default_tz_now_max() - timedelta(days=1)

    total_orders, created = Counter.objects.get_or_create(name="total_orders")
    total_orders.value = Order.objects.filter(type=OrderType.SHARED, debug=False, status=CHARGED).count()
    total_orders.save()

    money_saved, created = Counter.objects.get_or_create(name="money_saved")

    if not start_date:
        money_saved.value = 0
        money_saved.save()
        logging.info("fresh calculation - until %s" % end_date)
    else:
        if money_saved.modify_date > end_date:
            msg = "money saved already calculated: %s < %s" % (money_saved.modify_date, end_date)
            logging.error(msg)
            return HttpResponseBadRequest(msg)

        logging.info("from %s - until %s" % (start_date, end_date))

    deferred.defer(do_calc, start_date, end_date, _queue="maintenance")

    return HttpResponse("OK")

def do_calc(start_date, end_date, start=None, batch_size=100, count=0):
    from djangoappengine.db.utils import get_cursor, set_cursor

    if start_date:
        query = Order.objects.filter(create_date__gt=start_date, create_date__lt=end_date, type=OrderType.SHARED, debug=False)
    else:
        query = Order.objects.filter(create_date__lt=end_date, type=OrderType.SHARED, debug=True)

    if start:
        logging.info("start cursor = %s" % start)
        orders = set_cursor(query, start)
    else:
        orders = query

    orders = orders[0:batch_size]
    try:
        cursor = get_cursor(orders)
    except :
        logging.error(traceback.format_exc())
        return

    money_saved = Counter.objects.get(name="money_saved")

    for order in orders:
        try:
            count += 1
            if order.status not in [APPROVED, CHARGED]:
                logging.info("skipping order [%s]" % order.id)
                continue

            logging.info("calc: order [%s]" % order.id)

            if not order.price_alone:
                logging.warning("no price_alone for [%s]" % order.id)

        except :
            logging.error("Error while calculating price for order: [%s]\n%s" % (order.id, traceback.format_exc()))

        if order.price_alone:
            order_savings = order.price_alone - order.price
            logging.info("order [%s] saved: %s" % (order.id, order_savings))
            if order_savings > 0:
                money_saved.value += order_savings
                logging.info("money saved updated: %s" % money_saved.value)
            elif order_savings < 0:
                logging.warning("negative savings for order [%s]" % order.id)
        else:
            logging.warning("price calculation failed: %s" % order.id)


    money_saved.save()
    logging.info("processed %s entities" % count)
    if orders:
        deferred.defer(do_calc, start_date, end_date, start=cursor, count=count, _queue="maintenance")
    else:
        logging.info("ALL DONE: %s" % count)

