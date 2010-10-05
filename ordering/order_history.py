from ordering.models import Order
from django.core.paginator import Paginator, InvalidPage, EmptyPage
from types import MethodType
import logging
from datetime import datetime
from django.utils.translation import ugettext

PAGE_SIZE = 5

ORDER_HISTORY_COLUMNS = ["Date", "From", "To", "Station"]
ORDER_HISTORY_COLUMN_NAMES = [ugettext(s) for s in ORDER_HISTORY_COLUMNS]
ORDER_HISTORY_FIELDS = ["create_date", "from_raw", "to_raw", "station_name"]


def get_orders_history(passenger, page=1, keywords=None, sort_by=None, sort_dir=None):
    query = Order.objects.filter(passenger=passenger)
    # Unfortunately, we need to separate the logic of retrieving orders with or without textual search,
    # because in AppEngine: "Properties In Inequality Filters Must Be Sorted Before Other Sort Orders"
    # See: http://code.google.com/appengine/docs/python/datastore/queriesandindexes.html
    if keywords:
        # Unfortunately too, only AND filters are supported, so we can't use Q objects
        query = set(list(query.filter(from_raw__icontains=keywords)) + list(query.filter(to_raw__icontains=keywords)))

        logging.debug("Searching by %s. Ordering by %s%s" % (keywords or "", sort_dir, sort_by))
        
        # need manually do the sorting in-memory
        d = {}
        for o in query:
            sort_by_value = getattr(o, sort_by)
            if isinstance(sort_by_value, datetime):
                sort_by_value = sort_by_value.strftime("%Y/%m/%d-%H:%M:%S:%f")
            while sort_by_value in d:
                sort_by_value = "%s_" % sort_by_value
            d[sort_by_value] = o

        s = sorted(d)
        if sort_dir == "-":
            s = reversed(s)
        query = [d[key] for key in s]
    else:
        # no search
        if sort_by:
            query = query.filter(**{str("%s__isnull" % sort_by): False})
            query = query.order_by("%s%s" % (sort_dir, sort_by))

        logging.debug("Ordering by %s%s" % (sort_dir, sort_by))

    paginator = Paginator(query, PAGE_SIZE)

    # If page request (9999) is out of range, deliver last page of results.
    try:
        orders_page = paginator.page(page)
    except (EmptyPage, InvalidPage):
        orders_page = paginator.page(paginator.num_pages)

    # Dump the Page attributes we want to a dictionary
    serializedpage = {}
    serializedpage["page_size"] = len(orders_page.object_list)
    wanted = ("end_index", "has_next", "has_other_pages", "has_previous",
            "next_page_number", "number", "start_index", "previous_page_number")
    for attr in wanted:
        v = getattr(orders_page, attr)
        if isinstance(v, MethodType):
            serializedpage[attr] = v()
        elif isinstance(v, (str, int)):
            serializedpage[attr] = v

    if keywords and len(query) <= PAGE_SIZE:
        serializedpage["has_other_pages"] = False
        serializedpage["has_next"] = False
        serializedpage["has_previous"] = False
        serializedpage["page"] = 1

    serializedpage["keywords"] = keywords or ""
    
    orders = []
    for order in orders_page.object_list:
        record = {}
        for i, col in enumerate(ORDER_HISTORY_COLUMNS):
            record[col] = getattr(order, ORDER_HISTORY_FIELDS[i])
        record["Id"] = order.id
        
        orders.append(record)

    serializedpage["object_list"] = orders
    
    return serializedpage


