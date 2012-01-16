from ordering.models import Order, ACCEPTED, OrderAssignment, REJECTED, NOT_TAKEN, IGNORED, ASSIGNMENT_STATUS
from django.core.paginator import Paginator, InvalidPage, EmptyPage
from types import MethodType
import logging
from datetime import datetime
from django.utils.translation import ugettext, ugettext_lazy
PAGE_SIZE = 10

ORDER_HISTORY_COLUMNS =         ["Date", "From", "To", "Station", "Passenger Rating"]
ORDER_HISTORY_COLUMN_NAMES =    [ugettext_lazy("Date"), ugettext_lazy("From"), ugettext_lazy("To"), ugettext_lazy("Station"), ugettext_lazy("Passenger Rating")]
ORDER_HISTORY_FIELDS =          ["create_date", "from_raw", "to_raw", "station_name", "passenger_rating"]

BUSINESS_ORDER_HISTORY_COLUMNS =         ["Date", "From", "To", "Station", "Passenger Details" ,"Comments"]
BUSINESS_ORDER_HISTORY_COLUMN_NAMES =    [ugettext_lazy("Date"), ugettext_lazy("From"), ugettext_lazy("To"), ugettext_lazy("Station"), ugettext_lazy("Passenger Details"), ugettext_lazy("Comments")]
BUSINESS_ORDER_HISTORY_FIELDS =          ["create_date", "from_raw", "to_raw", "station_name", "taxi_is_for", "comments"]

STATION_ORDER_HISTORY_COLUMNS =         ["Date", "From", "To", "Passenger Phone"]
STATION_ORDER_HISTORY_COLUMN_NAMES =    [ugettext_lazy("Date"), ugettext_lazy("From"), ugettext_lazy("To"), ugettext_lazy("Passenger Phone")]
STATION_ORDER_HISTORY_FIELDS =          ["create_date", "from_raw", "to_raw", "passenger_phone"]

STATION_ASSIGNMENT_HISTORY_COLUMNS =         ["Date", "From", "To", "dn_business_name", "status", "status_label"]
STATION_ASSIGNMENT_HISTORY_COLUMN_NAMES =    [ugettext_lazy("Date"), ugettext_lazy("From"), ugettext_lazy("To"), ugettext_lazy("Passenger"), "_HIDDEN", ugettext_lazy("Status Label")]
STATION_ASSIGNMENT_HISTORY_FIELDS =          ["create_date", "dn_from_raw", "dn_to_raw", "dn_business_name", "status", "status"]

def get_orders_history(passenger, page=1, keywords=None, sort_by=None, sort_dir=None):
    query = Order.objects.filter(passenger=passenger).filter(status=ACCEPTED)
    if passenger.business:
        columns = BUSINESS_ORDER_HISTORY_COLUMNS
        fields = BUSINESS_ORDER_HISTORY_FIELDS
    else:
        columns = ORDER_HISTORY_COLUMNS
        fields = ORDER_HISTORY_FIELDS
    return get_orders_history_data(query, columns, fields,
                                   page, keywords, sort_by, sort_dir)

def get_stations_orders_history_data(station, page=1, keywords=None, sort_by=None, sort_dir=None):
    query = Order.objects.filter(station_id=station.id)
    return get_orders_history_data(query, STATION_ORDER_HISTORY_COLUMNS, STATION_ORDER_HISTORY_FIELDS,
                                   page, keywords, sort_by, sort_dir)

def get_stations_assignments_history_data(station, page=1, sort_by=None, sort_dir=None, start_date=None, end_date=None, status_list=None):
    query = OrderAssignment.objects.filter(station=station)
    if start_date:
        query = query.filter(create_date__gte=start_date)
    if end_date:
        query = query.filter(create_date__lte=end_date)
    if not status_list:
        query = query.filter(status__in=[NOT_TAKEN, REJECTED, IGNORED, ACCEPTED])
    elif IGNORED in status_list:
        query = query.filter(status__in=status_list+[NOT_TAKEN])  # not taken orders are counted as ignored
    else:
        query = query.filter(status__in=status_list)

    data = get_orders_history_data(query, columns=STATION_ASSIGNMENT_HISTORY_COLUMNS,
                                   fields=STATION_ASSIGNMENT_HISTORY_FIELDS, page=page, sort_by=sort_by,
                                   sort_dir=sort_dir)
    for obj in data['object_list']:
        obj['dn_business_name'] =  ugettext("Business") if obj['dn_business_name'] else ugettext("Private")
        for key, label in ASSIGNMENT_STATUS:
            if key == obj['status_label']:
                obj['status_label'] =  label
    return data

def get_orders_history_data(query, columns, fields, page=1, keywords=None, sort_by=None,
                            sort_dir=None):
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
    serializedpage["sort_by"] = sort_by
    serializedpage["sort_dir"] = sort_dir
    serializedpage["page_size"] = len(orders_page.object_list)
    serializedpage["num_pages"] = paginator.num_pages
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
        for i, col in enumerate(columns):
            # try calling the formatter method for a date field
            formatter = fields[i] + "_format"
            if fields[i].endswith("_date") and hasattr(order, formatter):
                record[col] = getattr(order, formatter).__call__()
            else:
                record[col] = getattr(order, fields[i])
        record["Id"] = order.id
        
        orders.append(record)

    serializedpage["object_list"] = orders
    
    return serializedpage


