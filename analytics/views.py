from common.tz_support import utc_now, default_tz_now
from django.views.decorators.csrf import csrf_exempt
from common.decorators import internal_task_on_queue, catch_view_exceptions
from django.http import HttpResponse
from django.db.models import get_model
from django.utils.translation import ugettext as _
from django.contrib.admin.views.decorators import staff_member_required
from django.conf import settings
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from ordering.models import Order, Station, ORDER_STATUS, OrderAssignment, ACCEPTED, REJECTED, WorkStation
from djangotoolbox.http import JSONResponse
from common.models import City, Country
from datetime import datetime, timedelta
from datetime import time as dt_time
import time
import logging
import sys

from analytics.forms import AnalyticsForm, AnalysisScope, AnalysisType
from models import AnalyticsEvent
from common.util import EventType

@csrf_exempt
@catch_view_exceptions
@internal_task_on_queue("log-events")
def log_event_on_queue(request):
    event = AnalyticsEvent()
    try:
        for key, val in request.POST.iteritems():
            if key == 'event_type':
                event.type = int(val)
            if key == 'rating' and val:
                event.rating = int(val)
            if key == 'lon' and val:
                event.lon = float(val)
            if key == 'lat' and val:
                event.lat = float(val)
            if key.endswith("_id") and val:
                model_name = key.split("_id")[0]
                model = get_model('ordering', "".join(model_name.split("_")))
                if not model:
                    model = get_model('common', model_name)

                instance = model.objects.filter(id=int(val)).get()
                setattr(event, model_name, instance)
        event.save()
    except:
        # catch the exception to avoid re-running of the task over and over. Log this as error.
        logging.error("Could not log event %s: %s" % (request.POST.get('event_type', "No event passed"), sys.exc_info()[1]))  
        return HttpResponse("NOT OK")
    else:
        return HttpResponse("OK")  


@staff_member_required
def analytics(request):
    telmap_user = settings.TELMAP_API_USER
    telmap_password = settings.TELMAP_API_PASSWORD
    if request.GET:
        form = AnalyticsForm(request.GET)
        if form.is_valid():
            result = {}
            scope_filter = None
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
            data_scope = int(form.cleaned_data['data_scope'])
            data_type = int(form.cleaned_data['data_type'])
            events = AnalyticsEvent.objects.filter(create_date__lte=end_date + timedelta(days=1), create_date__gte=start_date).order_by('create_date')

            if data_scope == AnalysisScope.CITY:
                scope_filter = int(form.cleaned_data['city'])
                events = events.filter(city=scope_filter)

            elif data_scope == AnalysisScope.STATION:
                scope_filter = int(form.cleaned_data['station'])
                events = events.filter(station=scope_filter)

            if data_type == AnalysisType.RATINGS:
                events = events.filter(type__in=AnalysisType.get_event_types(AnalysisType.RATINGS))
                if events:
                    result = {
                        'ratings' : get_rating_results(events),
                        'by_date':  get_results_by_day(events, start_date, end_date, rating_results=True),
                        'by_hour':  get_results_by_hour(events, start_date, end_date, rating_results=True)
                    }
            elif data_type == AnalysisType.ORDERS:
                events = events.filter(type__in=AnalysisType.get_event_types(AnalysisType.ORDERS))
                if events:
                    result = {
                        'by_date':  get_results_by_day(events, start_date, end_date),
                        'by_hour':  get_results_by_hour(events, start_date, end_date),
                        'by_type':  get_results_by_type(events, start_date, end_date),
                        'map_data':  get_map_results(events)
                    }
            elif data_type == AnalysisType.REGISTRATION:
                events = events.filter(type__in=AnalysisType.get_event_types(AnalysisType.REGISTRATION))
                if events:
                    result = {
                        'by_date':  get_results_by_day(events, start_date, end_date),
                        'by_hour':  get_results_by_hour(events, start_date, end_date),
                    }

            elif data_type == AnalysisType.TIMING:
                result = get_timing_results(start_date, end_date, data_scope, scope_filter)

            elif data_type == AnalysisType.ONLINE_STATUS:
                events = events.filter(type__in=AnalysisType.get_event_types(AnalysisType.ONLINE_STATUS), create_date__lte=end_date + timedelta(days=1), create_date__gte=start_date)#.order_by('create_date')
                if events:
                    result = {
                        'online_status': get_online_status_results(events, data_scope, scope_filter, end_date)
                    }
                    
            return JSONResponse(result)
    else:
        form = AnalyticsForm()

    return render_to_response("analytics.html", locals(), context_instance=RequestContext(request))

@staff_member_required
def update_scope_select(request):
    scope = int(request.GET.get("data_scope", -1))
    result = {}
    country = Country.objects.filter(code="IL").get() # TODO_WB allow for other countries.
    if scope == AnalysisScope.CITY: # return cities
        result['options'] = City.city_choices(country)
        result['target_id_selector'] = "#id_city"
    elif scope == AnalysisScope.STATION: # return stations
        result['options'] = Station.get_default_station_choices(include_empty_option=False)
        result['target_id_selector'] = "#id_station"

    return JSONResponse(result)

def get_online_status_results(events, data_scope, scope_filter, end_date):

    import time

    work_stations = WorkStation.objects.filter(was_installed=True)
    if data_scope == AnalysisScope.STATION:
        work_stations = work_stations.filter(station=scope_filter)

    offset = 0.1 * work_stations.count() + 1
    ws_offset = 0
    series = []
    for ws in work_stations:
        name = "%s #%s" % (ws.dn_station_name, ws.id)
        data = []
        ws_events = events.filter(work_station=ws)
        for event in ws_events:
            # date should be in javascript's Date() format
            data.append([time.mktime(event.create_date.timetuple()) * 1000,
                         (1 if event.type == EventType.WORKSTATION_UP else 0) + ws_offset])


        # add "fake" event at the end of the chart with the value of the last event
        ws_count = ws_events.count()
        if ws_count:
            last_event = ws_events[ws_count - 1]
            if utc_now().date() > end_date:
                end_time = datetime.combine(end_date, dt_time.max)
            else:
                end_time = default_tz_now()

            data.append([time.mktime(end_time.timetuple()) * 1000,
                         (1 if last_event.type == EventType.WORKSTATION_UP else 0) + ws_offset])

            ws_offset += offset
            series.append({'name': name, 'data': data})

    return {'title': 'Workstation online status', 'y_axis_title': 'Online status' ,'series': series}

def get_timing_results(start_date, end_date, data_scope, scope_filter):
    orders = []
    if data_scope == AnalysisScope.STATION:
        orders = OrderAssignment.objects.filter(station=scope_filter, create_date__lte=end_date + timedelta(days=1), create_date__gte=start_date).order_by('create_date')
    else:
        orders = OrderAssignment.objects.filter(create_date__lte=end_date + timedelta(days=1), create_date__gte=start_date).order_by('create_date')

    series = {
        "accepted": {
                'data': [],
                'name': _("Accepted"),
                'type': 'column'
        },
        "rejected": {
            'data': [],
            'name': _("Rejected"),
            'type': 'column'
        }
    }
    x_axis = []
    data = []
    for i, order in enumerate(orders):
#        logging.info(order.station)
        if order.status == ACCEPTED:
            series["accepted"]["data"].append((order.modify_date - order.create_date).seconds)
        elif order.status == REJECTED:
            series["rejected"]["data"].append((order.modify_date - order.create_date).seconds)

    accepted_data = series["accepted"]["data"]
    accepted_average = sum(accepted_data) / len(accepted_data) if accepted_data else 0
 
    rejected_data = series["rejected"]["data"]
    rejected_average = sum(rejected_data) / len(rejected_data) if rejected_data else 0

#        x_axis.append(i)
    return { "by_hour": {
        'series': [series["accepted"], series["rejected"]],
        'title':        _("Timing"),
        'y_axis_title': _("Response Time (sec)"),
        'labels': {
            "items": [  {"html": "%s: %s" % ("Accepted Average", accepted_average), "style": {
                "left": '50px',
                "top": '10px'
            }},
                        {"html": "%s: %s" % ("Rejected Average", rejected_average), "style": {
                "left": '50px',
                "top": '30px'
            }}]
        }
    }}

def get_map_results(events):
    map_events = [EventType.ORDER_ACCEPTED, EventType.ORDER_IGNORED, EventType.ORDER_REJECTED, EventType.NO_SERVICE_IN_CITY]

    result = {
        'markers':  [],
        'legend':   [ { 'name': EventType.get_label(e), 'icon': EventType.get_icon(e) } for e in map_events ]
    }

    for event in events:
        if event.lon and event.lat and event.type in map_events:
            result['markers'].append({
                'lon':      event.lon,
                'lat':      event.lat,
                'title':     "%s" % event.get_label(),
                'icon':     EventType.get_icon(event.type),
                'type':     event.get_label()
                })

    logging.info(result)        
    return result

def get_rating_results(events):
    rating_dic = {}
    all_ratings = 0
    rating_count = 0
    for event in events:
        if event.rating:
            rating_count += 1
            rating = event.rating
            all_ratings += rating
            if not rating in rating_dic:
                rating_dic[rating] = 1
            else:
                rating_dic[rating] += 1

    result = {
        'series': [{
            'data': [[str(rating), rating_dic[rating]] for rating in rating_dic],
            'name': _("Rating"),
            'type': 'pie'
        }],
        'avarage':  round(float(all_ratings) / rating_count, 2),
        'total':    rating_count
    }

    return result

def get_results_google(events):

    rows = []
    columns = [['date', 'Date']]
    labels = []
    for row_index, event in enumerate(events):
        label = event.get_label()
        if not label in labels:
            labels.append(label)
            columns.append(['number', label])

    for row_index, event in enumerate(events):
        label = event.get_label()
        row = []
        for col_index, column in enumerate(columns[1:]):
            if column[1] == label:
                row.append(1)
            else:
                row.append(0)

        row.insert(0, time.mktime(event.create_date.timetuple()) * 1000)
        rows.append(row)

    return {
        'columns':columns,
        'rows': rows,
    }

def get_results_by_day(events, start_date, end_date, rating_results=False):
    date_dic = {}
    total_label = _("Total")
    result = {
        'series':       [],
        'title':        _("Ratings - by Date") if rating_results else _("Orders - by Date"),
        'y_axis_title': _("Ratings") if rating_results else _("Orders")
        
    }
    for event in events:
        key = get_date_key(event.create_date)
        if rating_results:
            if not total_label in date_dic:
                date_dic[total_label] = {}

            if event.rating:
                label = event.rating
            else:
                continue
        else:
            label = event.get_label()
        if not label in date_dic:
            date_dic[label] = {}

        if key in date_dic[label]:
            date_dic[label][key] += 1
        else:
            date_dic[label][key] = 1

        if rating_results:
            if key in date_dic[total_label]:
                date_dic[total_label][key] += 1
            else:
                date_dic[total_label][key] = 1



    current_date = start_date

    while current_date <= end_date:
        key = get_date_key(current_date)
        for status in date_dic.keys():
            if not key in date_dic[status]:
                date_dic[status][key] = 0

        current_date += timedelta(days=1)

    for status in date_dic.keys():
        result['series'].append({
                                    'data':         [[key * 1000, date_dic[status][key]] for key in date_dic[status].keys()],
                                    'name':         status,
                                    'type':         'line',
                                    'pointStart':   start_date,
                                    'pointInterval':1000 * 3600 * 24
                                    })

    return result

def get_results_by_type(events, start_date, end_date):
    type_dic = {}
    for event in events:
        label = event.get_label()
        if not label in type_dic:
            type_dic[label] = 1
        else:
            type_dic[label] += 1

    result = {
        'series': [{
            'data': [[str(t), type_dic[t]] for t in type_dic],
            'type': 'pie'
        }],
        'name': _("Orders By Type"),
    }

    return result

def get_results_by_hour(events, start_date, end_date, rating_results=False):
    date_dic = {}
    total_label = _("Total")
    result = {
        'series':       [],
        'title':        _("Ratings - by Hour") if rating_results else _("Orders - by Hour"),
        'y_axis_title': _("Ratings") if rating_results else _("Orders")
    }
    for event in events:
        key = get_hour_key(event.create_date)
        if rating_results:
            if not total_label in date_dic:
                date_dic[total_label] = {}

            if event.rating:
                label = event.rating
            else:
                continue
        else:
            label = event.get_label()
        if not label in date_dic:
            date_dic[label] = {}

        if key in date_dic[label]:
            date_dic[label][key] += 1
        else:
            date_dic[label][key] = 1

        if rating_results:
           if key in date_dic[total_label]:
               date_dic[total_label][key] += 1
           else:
               date_dic[total_label][key] = 1


    days_interval = (end_date - start_date).days
    for i in range(0,24):
        for status in date_dic.keys():
            if i in date_dic[status]:
                date_dic[status][i] = float(date_dic[status][i]) / float(days_interval)
            else:
                date_dic[status][i] = 0


    for status in date_dic.keys():
        result['series'].append({
                                    'data':         [[str(key) + ":00", date_dic[status][key]] for key in date_dic[status].keys()],
                                    'name':         status,
                                    'type':         'line'
                                })

    return result

def get_date_key(date):
    day_resolution_date = datetime(date.year, date.month, date.day)
    return time.mktime(day_resolution_date.timetuple())

def get_hour_key(date):
    return date.hour
 
