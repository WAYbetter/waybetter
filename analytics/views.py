from django.views.decorators.csrf import csrf_exempt
from ordering.decorators import internal_task_on_queue
from django.http import HttpResponse
from django.db.models import get_model
from django.utils.translation import gettext as _
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from ordering.models import Order, Station, ORDER_STATUS
from djangotoolbox.http import JSONResponse
from common.models import City, Country
from datetime import datetime, timedelta
import time
import logging
import sys

from analytics.forms import AnalyticsForm, AnalysisScope, AnalysisType
from models import AnalyticsEvent
from common.util import EventType

@csrf_exempt
@internal_task_on_queue("log-events")
def log_event_on_queue(request):
    event = AnalyticsEvent()
    try:
        for key, val in request.POST.iteritems():
            if key == 'event_type':
                event.type = int(val)
            if key == 'rating' and val:
                event.rating = int(val)
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
    if request.GET:
        form = AnalyticsForm(request.GET)
        if form.is_valid():
            result = {}
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
            
            events = AnalyticsEvent.objects.filter(create_date__lte=end_date + timedelta(days=1), create_date__gte=start_date).order_by('create_date')
            if int(form.cleaned_data['data_scope']) == AnalysisScope.CITY:
                events = events.filter(city=int(form.cleaned_data['city']))

            elif int(form.cleaned_data['data_scope']) == AnalysisScope.STATION:
                events = events.filter(station=int(form.cleaned_data['station']))

            if int(form.cleaned_data['data_type']) == AnalysisType.RATINGS: 
                events = events.filter(type__in=AnalysisType.get_event_types(AnalysisType.RATINGS))
                if events:
                    result = {
                        'ratings' : get_rating_results(events),
                        'by_date':  get_results_by_day(events, start_date, end_date),
                        'by_hour':  get_results_by_hour(events, start_date, end_date)
                    }
            elif int(form.cleaned_data['data_type']) == AnalysisType.ORDERS: 
                events = events.filter(type__in=AnalysisType.get_event_types(AnalysisType.ORDERS))
                if events:
                    result = {
                        'by_date':  get_results_by_day(events, start_date, end_date),
                        'by_hour':  get_results_by_hour(events, start_date, end_date)
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
    if scope == 1: # return cities

        result['options'] = City.city_choices(country)
        result['target_id_selector'] = "#id_city"
    elif scope == 2: # return stations
        result['options'] = Station.get_default_station_choices(include_empty_option=False)
        result['target_id_selector'] = "#id_station"

    return JSONResponse(result)

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



def get_results_by_day(events, start_date, end_date):
    date_dic = {}
    total_label = _("Total")
    calc_total = False
    result = {
        'series': []
    }
    for event in events:
        key = get_date_key(event.create_date)
        if event.type == EventType.ORDER_RATED:
            if not total_label in date_dic:
                date_dic[total_label] = {}
                calc_total = True

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

        if calc_total:
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
                                    'type':         'spline',
                                    'pointStart':   start_date,
                                    'pointInterval':1000 * 3600 * 24
                                    })

    logging.info(result['series'])
    return result

def get_results_by_hour(events, start_date, end_date):
    date_dic = {}
    total_label = _("Total")
    calc_total = False
    result = {
        'series': []
    }
    for event in events:
        key = get_hour_key(event.create_date)
        if event.type == EventType.ORDER_RATED:
            if not total_label in date_dic:
                date_dic[total_label] = {}
                calc_total = True

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

        if calc_total:
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
                                    'type':         'spline'
                                })

    logging.info(result['series'])
    return result




def get_date_key(date):
    day_resolution_date = datetime(date.year, date.month, date.day)
    return time.mktime(day_resolution_date.timetuple())

def get_hour_key(date):
    return date.hour
 
