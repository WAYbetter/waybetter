from google.appengine.api import channel
from common.geocode import geocode
from common.langsupport.util import translate_to_ws_lang
from common.models import Country, City
from common.forms import DatePickerForm
from common.util import get_model_from_request, custom_render_to_response, notify_by_email, get_current_version, get_channel_key, blob_to_image_tag, is_in_hebrew, ga_hit_page, ga_track_event
from decorators import station_required
from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import AuthenticationForm
from django.core.urlresolvers import reverse
from django.forms.models import inlineformset_factory
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect, HttpResponseForbidden, HttpResponseNotFound
from django.shortcuts import render_to_response, get_object_or_404
from django.template.context import RequestContext
from django.utils import simplejson
from django.utils.translation import ugettext as _, get_language_from_request
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from djangotoolbox.http import JSONResponse
from ordering.decorators import work_station_required, station_or_workstation_required, NOT_A_PASSENGER, NOT_A_USER
from ordering.errors import ShowOrderError, UpdateOrderError
from ordering.forms import StationProfileForm, PhoneForm, OrderForm, INITIAL_DATA, HIDDEN_FIELDS
from ordering.models import  OrderAssignment, Station, WorkStation, Passenger, CURRENT_PASSENGER_KEY, ORDER_ASSIGNMENT_TIMEOUT, ORDER_TEASER_TIMEOUT
from ordering.util import safe_delete_user
from ordering.order_history import STATION_ORDER_HISTORY_COLUMNS, STATION_ORDER_HISTORY_COLUMN_NAMES, STATION_ORDER_HISTORY_FIELDS, STATION_ASSIGNMENT_HISTORY_COLUMNS, STATION_ASSIGNMENT_HISTORY_COLUMN_NAMES, STATION_ASSIGNMENT_HISTORY_FIELDS,  get_stations_orders_history_data, get_stations_assignments_history_data

import re
import datetime
import logging
import models
import order_manager
import order_tracker
import station_connection_manager

try: # DeadlineExceededError can live in two different places
    # When deployed
    from google.appengine.runtime import DeadlineExceededError
except ImportError:
    from google.appengine.runtime.apiproxy_errors import DeadlineExceededError
    # In the development server

qr_regexp = re.compile("/qr/\w*/*")

ACCEPT = "accept"
REJECT = "reject"
ONLINE = "online"
OFFLINE = "offline"

# order assignment status
PENDING  = models.PENDING
ASSIGNED = models.ASSIGNED

STATION_DOMAINS = ["taxiapp.co.il"]

@station_required
def get_cities_for_country(request, station):
    selected_city = None
    try:
        c = Country.objects.filter(id=request.GET.get('country_id', '0')).get()
    except Country.DoesNotExist:
        return HttpResponseBadRequest('Invalid country passed')

    if station.country == c:
        selected_city = station.city.id

    result = { "options": City.city_choices(c) }
    if selected_city:
        result.update({ "selected_option": selected_city })

    return JSONResponse(result)

@station_required
def resolve_address(request, station):
    try:
        city = City.objects.filter(id=request.GET.get('city_id', '-1')).get()
    except City.DoesNotExist:
        return HttpResponseBadRequest(_("Invalid city"))

    address = request.GET.get('address', None)
    if not address:
        return JSONResponse('')

    return JSONResponse(geocode(address, constrain_to_city=city))

@station_required
def station_profile(request, station):

    extra = 1 if station.phones.count() == 0 else 0
    PhoneFormSetX = inlineformset_factory(models.Station, models.Phone, extra=extra, can_delete=True, form=PhoneForm)

    if request.method == 'POST':
        phone_formset = PhoneFormSetX(request.POST, instance=station)
        form = StationProfileForm(request.POST, request.FILES)
        if form.is_valid() and phone_formset.is_valid():
            save_user = False
            save_station = False

            user = station.user

            if user.email != form.cleaned_data["email"]:
                user.email = form.cleaned_data["email"]
                save_user = True

            if "password" in form.cleaned_data and len(form.cleaned_data["password"]) > 0:
                user.set_password(form.cleaned_data["password"])
                save_user = True

            if save_user: user.save()

            if "logo" in request.FILES:
                station.logo = request.FILES['logo'].read()
                save_station = True


            for field in ("name", "country", "city", "address", "number_of_taxis", "website_url", "description", "lon", "lat"):
                if field in form.cleaned_data and getattr(station, field) != form.cleaned_data[field]:
                    setattr(station, field, form.cleaned_data[field])
                    save_station = True

            if save_station: station.save()

            phone_formset.save()
            response = ''
        else: # form is invalid
            errors  = [{ e: form.errors.get(e) } for e in form.errors.keys()]
            for i, form_errors in enumerate(phone_formset.errors):
                if form_errors:
                    errors.extend([{ "%s-%d-%s" % (phone_formset.prefix, i, e): form_errors.get(e) } for e in form_errors.keys()])

            response = {"errors": errors}

        if request.is_ajax():
            return JSONResponse(response)
        else:
            # this means the jquery form plugin used an iframe to submit a file. need to wrap json with textarea
            # see: http://jquery.malsup.com/form/#file-upload
            return HttpResponse("<textarea>%s</textarea>" % simplejson.dumps(response))

    else: # GET - render the form
        phone_formset = PhoneFormSetX(instance=station)
        data = station.__dict__
        data.update(station.user.__dict__)
        data[INITIAL_DATA] = True
        del data['password']

        form = StationProfileForm(data)

    return render_to_response("station_profile.html", locals(),
                              context_instance=RequestContext(request))

@station_required
def download_workstation(request, station):
    workstations = station.work_stations.all()
    indexed_workstations = [(i+1, ws) for i, ws in enumerate(workstations)]
    workstations_list = []
    for i, ws in indexed_workstations:
        if ws.was_installed:
            status = "connected"
        else:
            status = "disconnected"
        workstations_list.append((i, ws, status))
    return render_to_response("workstation_download.html", locals())
#    return HttpResponse("test")

def login_workstation(request):
    token = request.POST.get('token')
    next = request.POST.get('next')
    logging.info("logging in WS: '%s'" % token)
    workstation = get_object_or_404(WorkStation, token=token)

    # next url must end with the correct workstation id
    r = re.compile("/(\d+)/?$")
    m = r.search(next)
    if not m or m.group(1) != str(workstation.id):
        return HttpResponseForbidden("Wrong workstation")

    user = workstation.user
    user.backend = 'django.contrib.auth.backends.ModelBackend'  # could also be fetched from the list in settings.
    #username, password = workstation.user.username, workstation.user.password
    #user = authenticate(username=username, password=password)
    if user:
        login(request, user)
        return HttpResponseRedirect(next)
    else:
        logging.info("returning 403")
        return HttpResponseForbidden("invalid login credentials")

@csrf_exempt
def workstation_auth(request):
    token = request.POST.get('token')
    logging.info("check_auth: token = '%s'" % token)
    workstation = get_object_or_404(WorkStation, token=token)
    if not workstation.was_installed:
        workstation.was_installed = True
        workstation.save()
    return HttpResponse("Ok")

@csrf_exempt
@station_required
def delete_workstation(request, station):
    token = request.POST.get('token')
    workstation = get_object_or_404(WorkStation, token=token, station=station)
    user = workstation.user
    workstation.delete()
    safe_delete_user(user)
    station.build_workstations()

    return HttpResponse("Ok")

@work_station_required
def workstation_home(request, work_station, workstation_id):
#    if not random.randint(0, 1):
#        return HttpResponseBadRequest("Just a test")

    if work_station.station.subdomain_name not in ["ny", "media"]:
        shutdown = True

    request.session["django_language"] = "he" # hardcode hebrew for stations
    show_version_error = True and not settings.LOCAL

    air_version = re.search("AdobeAIR/([\d.]+)", request.META.get("HTTP_USER_AGENT", ""))
    if air_version:
        if air_version.groups()[0] >= "3.0.0":
            show_version_error = False

    if work_station.id != int(workstation_id):
        logout(request)
        return HttpResponseRedirect(request.path)
    station_name = work_station.station.name
    station_rating = work_station.station.average_rating
    polling_interval = settings.POLLING_INTERVAL
    pending = PENDING
    assigned = ASSIGNED
    accept = ACCEPT
    reject = REJECT
    online = ONLINE
    offline = OFFLINE
    pickup_times = [1, 3, 5, 7, 10, 15, 20]
    timeout_interval = ORDER_ASSIGNMENT_TIMEOUT - 1
    teaser_interval = ORDER_TEASER_TIMEOUT - 1
    heartbeat_timeout_interval = 1000 * models.WORKSTATION_HEARTBEAT_TIMEOUT_INTERVAL
    is_popup = True
    station_rating = work_station.station.average_rating
    connection_check_key = station_connection_manager.CONNECTION_CHECK_KEY
    connection_check_interval = station_connection_manager.CONNECTION_CHECK_INTERVAL
    token = channel.create_channel(work_station.generate_new_channel_id())
    current_version = get_current_version()
    return render_to_response("workstation_home.html", locals())

@work_station_required
def current_version(request, work_station):
    if work_station.is_online:
        return JSONResponse(get_current_version())
    else:
        return JSONResponse(0) # cause a refresh of the module

@work_station_required
def get_workstation_orders(request, work_station):
    order_assignments_for_ws = OrderAssignment.objects.filter(work_station = work_station, status = models.ASSIGNED)
    return JSONResponse(OrderAssignment.serialize_for_workstation(order_assignments_for_ws))


@work_station_required
def connected(request, work_station):
    station_connection_manager.workstation_connected(work_station.channel_id)
    return HttpResponse("OK")

@csrf_exempt
@work_station_required
def update_online_status(request, work_station):
    status = request.POST.get("status", "")
    val = work_station.accept_orders

    if status == ONLINE:
        val = True

    if status == OFFLINE:
        val = False


    if val != work_station.accept_orders:
        work_station.accept_orders = val
        work_station.save()

    logging.info("update_online_status: workstation %d to %s" % (work_station.id, status))
    return HttpResponse(str(work_station.accept_orders))

@csrf_exempt
@work_station_required
def show_order(request, work_station):
    order_id = request.POST.get("order_id")

    if order_id == station_connection_manager.DUMMY_ID:
        return JSONResponse({"pk": order_id,
                             "status": ASSIGNED,
                             "from_raw": translate_to_ws_lang(station_connection_manager.DUMMY_ADDRESS, work_station),
                             "seconds_passed": 5})

    order_id = int(order_id)
    try:
        order_assignment = order_manager.show_order(order_id, work_station)
    except ShowOrderError:
        logging.error("ShowOrderError")
        return HttpResponseBadRequest("ShowOrderError")

    result = OrderAssignment.serialize_for_workstation(order_assignment, base_time=order_assignment.show_date)
    return JSONResponse(result)

@csrf_exempt
@work_station_required
def update_order_status(request, work_station):
    new_status = request.POST.get("status")
    order_id = request.POST.get("order_id")
    if order_id == station_connection_manager.DUMMY_ID:
        return JSONResponse({'order_id': order_id, "order_status": "stale"})

    order_id = int(order_id)
    logging.info(request.POST)
    pickup_time = int(request.POST.get("pickup_time", 0))

    try:
        result = order_manager.update_order_status(order_id, work_station, new_status, pickup_time)
        return JSONResponse(result)
    except UpdateOrderError:
        return HttpResponseBadRequest("Invalid status")

@station_or_workstation_required
def get_station_orders_history(request, station):

#    is_popup = True
    use_external_css = True
    order_history_columns =  simplejson.dumps([unicode(s) for s in STATION_ORDER_HISTORY_COLUMNS])
    order_history_column_names = simplejson.dumps([unicode(s) for s in STATION_ORDER_HISTORY_COLUMN_NAMES])
    order_history_fields = simplejson.dumps([unicode(s) for s in STATION_ORDER_HISTORY_FIELDS])
    history_data_url = reverse('ordering.station_controller.get_station_orders_history_data')
    rating_choices = simplejson.dumps([{"val": c[0], "name": c[1]} for c in models.RATING_CHOICES])
    rating_disabled = True
    if request.META.has_key("HTTP_USER_AGENT"):
        workstation_agent = "adobeair" in request.META["HTTP_USER_AGENT"].lower()
    return render_to_response("orders_history.html", locals())

@csrf_exempt
@station_or_workstation_required
def get_station_orders_history_data(request, station):
    keywords = request.GET.get("keywords", None)
    page = int(request.GET.get("page", "1"))
    sort_by = request.GET.get("sort_by", "create_date")
    sort_dir = request.GET.get("sort_dir", "-")
    data = get_stations_orders_history_data(station, page, keywords, sort_by, sort_dir)
    return JSONResponse(data)

#@user_passes_test(lambda u: u.is_authenticated(), login_url=settings.STATION_LOGIN_URL)
@station_required
def station_home(request, station):
    return render_to_response("station_home.html", locals(), RequestContext(request))


@station_or_workstation_required
def station_analytics(request, station):
    is_popup = True
    if request.META.has_key("HTTP_USER_AGENT"):
        workstation_agent = "adobeair" in request.META["HTTP_USER_AGENT"].lower()

    if request.POST: # date picker form submitted
        form = DatePickerForm(request.POST)
        if form.is_valid():
            start_date = datetime.datetime.combine(form.cleaned_data["start_date"], datetime.time.min)
            end_date = datetime.datetime.combine(form.cleaned_data["end_date"], datetime.time.max)
            assignments = OrderAssignment.objects.filter(station=station, create_date__gte=start_date, create_date__lte=end_date)
            pie_data, total_count = get_station_assignments_pie_data(assignments)
            return JSONResponse({'pie_data': pie_data, 'total_count': total_count})
        else:
            return JSONResponse({'error': 'error'})

    else:
        station_name = station.name
        form = DatePickerForm()
        accepted = models.ACCEPTED
        ignored = models.IGNORED
        not_taken = models.NOT_TAKEN
        rejected = models.REJECTED

        order_history_columns =  simplejson.dumps([unicode(s) for s in STATION_ASSIGNMENT_HISTORY_COLUMNS])
        order_history_column_names = simplejson.dumps([unicode(s) for s in STATION_ASSIGNMENT_HISTORY_COLUMN_NAMES])
        order_history_fields = simplejson.dumps([unicode(s) for s in STATION_ASSIGNMENT_HISTORY_FIELDS])

        end_date = datetime.datetime.combine(datetime.date.today(), datetime.time.max)
        start_date = datetime.datetime.combine(end_date - datetime.timedelta(weeks=1), datetime.time.min)
        assignments = OrderAssignment.objects.filter(station=station, create_date__gte=start_date, create_date__lte=end_date)
        pie_data, total_count = get_station_assignments_pie_data(assignments)
        pie_data = simplejson.dumps(pie_data)

        # stringify the dates to the format used in the page
        start_date, end_date = start_date.strftime("%d/%m/%Y"), end_date.strftime("%d/%m/%Y")
        return custom_render_to_response("station_analytics.html", locals(), context_instance=RequestContext(request))


def get_station_assignments_pie_data(assignments):
    accepted_count = assignments.filter(status__in=[models.ACCEPTED]).count()
    ignored_count = assignments.filter(status__in=[models.IGNORED, models.NOT_TAKEN]).count()
    rejected_count = assignments.filter(status__in=[models.REJECTED]).count()

    pie_data = [{'name': _("Accepted"), 'color': '#2D9609', 'y': accepted_count},
            {'name': _("Ignored"), 'color': '#BA0909', 'y': ignored_count},
            {'name': _("Rejected"), 'color': '#FF7E00', 'y': rejected_count}]

    total_count = accepted_count + ignored_count + rejected_count
    return pie_data, total_count

@csrf_exempt
@station_or_workstation_required
def get_station_assignments_history_data(request, station):
    page = int(request.GET.get("page", "1"))
    sort_by = request.GET.get("sort_by", "create_date")
    sort_dir = request.GET.get("sort_dir", "-")

    status_list = request.GET.get("status_list", None)
    if status_list:
        status_list = simplejson.loads(status_list)

    start_date = request.GET.get("start_date", None)
    end_date = request.GET.get("end_date", None)
    if start_date and end_date:
        form = DatePickerForm({'start_date': start_date, 'end_date': end_date})
        if form.is_valid():
            start_date = datetime.datetime.combine(form.cleaned_data["start_date"], datetime.time.min)
            end_date = datetime.datetime.combine(form.cleaned_data["end_date"], datetime.time.max)

    data = get_stations_assignments_history_data(station, page=page, sort_by=sort_by, sort_dir=sort_dir, start_date=start_date, end_date=end_date, status_list=status_list)
    return JSONResponse(data)

def stations_home(request):
    station = get_model_from_request(models.Station, request)
    next = reverse(station_home)
    if station:
        return HttpResponseRedirect(next)

    form = AuthenticationForm()
    return render_to_response("station_home.html", locals(), RequestContext(request))

ALERT_DELTA = datetime.timedelta(minutes=30)
WS_DECEASED = "WS_DECEASED"
WS_BORN = "WS_BORN"
OK = "OK"

@csrf_exempt
@work_station_required
def message_received(request, work_station):
    logging.info("message_received by work_station #%d: %s" % (work_station.id,  request.POST))
    return HttpResponse("OK")

@csrf_protect
def station_page(request, subdomain_name):
    station = get_object_or_404(models.Station, subdomain_name=subdomain_name)

    ua = request.META.get("HTTP_USER_AGENT", "").lower()

    if station.market_app_url and ua.find("android") > -1:
        ga_hit_page(request)
        return HttpResponseRedirect(station.market_app_url)
    elif station.itunes_app_url and ua.find("iphone") > -1:
        ga_hit_page(request)
        return HttpResponseRedirect(station.itunes_app_url)

    passenger = Passenger.from_request(request)
    if passenger and passenger.business:
        return station_business_page(request, subdomain_name)

    if not request.mobile and CURRENT_PASSENGER_KEY in request.session:
        del request.session[CURRENT_PASSENGER_KEY]

    page_specific_class = "station_page"
    hidden_fields = HIDDEN_FIELDS
    form = OrderForm()
    not_a_user, not_a_passenger = NOT_A_USER, NOT_A_PASSENGER
    waze_token = settings.WAZE_API_TOKEN
    telmap_user = settings.TELMAP_API_USER
    telmap_password = settings.TELMAP_API_PASSWORD
    telmap_languages = 'he' if str(get_language_from_request(request)) == 'he' else 'en'
    country_code = settings.DEFAULT_COUNTRY_CODE
    station_full_name = _("%s Taxi station") % station.name
    website_link = station.get_station_page_link()
    pretty_website_link = website_link.replace("http://", "")
    station_logo = blob_to_image_tag(station.logo)

    if not passenger and request.GET.get("show_login", False):
        show_login = True

    return custom_render_to_response("station_page.html", locals(), context_instance=RequestContext(request))

@csrf_protect
def station_business_page(request, subdomain_name=None):
    if not subdomain_name:
        subdomain_name = get_station_domain(request)
    station = get_object_or_404(models.Station, subdomain_name=subdomain_name)
    passenger = Passenger.from_request(request)

    if not passenger:
        return auth_views.login(request, template_name="business_login.html")
#    only in django 1.3
#        return auth_views.login(request, template_name="business_login.html", extra_context={'station': station})
    elif not passenger.business:
        return HttpResponseForbidden("You are not a business")

    business = passenger.business
    cities = City.objects.filter(country=passenger.country)
    cities = filter(lambda city: is_in_hebrew(city.name), cities)
    cities = sorted(cities, key=lambda city: city.name)

    PENDING = models.PENDING
    ASSIGNED = models.ASSIGNED
    ACCEPTED = models.ACCEPTED
    ORDER_FAILED = models.FAILED # groups together FAILED, ERROR and TIMED_OUT
    ORDER_MAX_WAIT_TIME = models.ORDER_MAX_WAIT_TIME
    FAILED_MSG = _(order_tracker.STATUS_MESSAGES[models.FAILED])

    channel_key = get_channel_key(Passenger.from_request(request), request.session.session_key)
    passenger.cleanup_session_keys()
    passenger.session_keys.append(request.session.session_key)
    passenger.save()

    init_token = channel.create_channel(channel_key)
    init_tracker_history = [simplejson.dumps(msg) for msg in order_tracker.get_tracker_history(passenger)]

    return custom_render_to_response("station_page_business.html", locals(), context_instance=RequestContext(request))


def station_mobile_redirect(request, subdomain_name):
    try:
        Station.objects.get(subdomain_name=subdomain_name)
        # taken from http://detectmobilebrowser.com/ 30 June 2010
        base_script = "(function(a,b){if(/android|avantgo|blackberry|blazer|compal|elaine|fennec|hiptop|iemobile|ip(hone|od)|iris|kindle|lge |maemo|midp|mmp|opera m(ob|in)i|palm( os)?|phone|p(ixi|re)\/|plucker|pocket|psp|symbian|treo|up\.(browser|link)|vodafone|wap|windows (ce|phone)|xda|xiino/i.test(a)||/1207|6310|6590|3gso|4thp|50[1-6]i|770s|802s|a wa|abac|ac(er|oo|s\-)|ai(ko|rn)|al(av|ca|co)|amoi|an(ex|ny|yw)|aptu|ar(ch|go)|as(te|us)|attw|au(di|\-m|r |s )|avan|be(ck|ll|nq)|bi(lb|rd)|bl(ac|az)|br(e|v)w|bumb|bw\-(n|u)|c55\/|capi|ccwa|cdm\-|cell|chtm|cldc|cmd\-|co(mp|nd)|craw|da(it|ll|ng)|dbte|dc\-s|devi|dica|dmob|do(c|p)o|ds(12|\-d)|el(49|ai)|em(l2|ul)|er(ic|k0)|esl8|ez([4-7]0|os|wa|ze)|fetc|fly(\-|_)|g1 u|g560|gene|gf\-5|g\-mo|go(\.w|od)|gr(ad|un)|haie|hcit|hd\-(m|p|t)|hei\-|hi(pt|ta)|hp( i|ip)|hs\-c|ht(c(\-| |_|a|g|p|s|t)|tp)|hu(aw|tc)|i\-(20|go|ma)|i230|iac( |\-|\/)|ibro|idea|ig01|ikom|im1k|inno|ipaq|iris|ja(t|v)a|jbro|jemu|jigs|kddi|keji|kgt( |\/)|klon|kpt |kwc\-|kyo(c|k)|le(no|xi)|lg( g|\/(k|l|u)|50|54|e\-|e\/|\-[a-w])|libw|lynx|m1\-w|m3ga|m50\/|ma(te|ui|xo)|mc(01|21|ca)|m\-cr|me(di|rc|ri)|mi(o8|oa|ts)|mmef|mo(01|02|bi|de|do|t(\-| |o|v)|zz)|mt(50|p1|v )|mwbp|mywa|n10[0-2]|n20[2-3]|n30(0|2)|n50(0|2|5)|n7(0(0|1)|10)|ne((c|m)\-|on|tf|wf|wg|wt)|nok(6|i)|nzph|o2im|op(ti|wv)|oran|owg1|p800|pan(a|d|t)|pdxg|pg(13|\-([1-8]|c))|phil|pire|pl(ay|uc)|pn\-2|po(ck|rt|se)|prox|psio|pt\-g|qa\-a|qc(07|12|21|32|60|\-[2-7]|i\-)|qtek|r380|r600|raks|rim9|ro(ve|zo)|s55\/|sa(ge|ma|mm|ms|ny|va)|sc(01|h\-|oo|p\-)|sdk\/|se(c(\-|0|1)|47|mc|nd|ri)|sgh\-|shar|sie(\-|m)|sk\-0|sl(45|id)|sm(al|ar|b3|it|t5)|so(ft|ny)|sp(01|h\-|v\-|v )|sy(01|mb)|t2(18|50)|t6(00|10|18)|ta(gt|lk)|tcl\-|tdg\-|tel(i|m)|tim\-|t\-mo|to(pl|sh)|ts(70|m\-|m3|m5)|tx\-9|up(\.b|g1|si)|utst|v400|v750|veri|vi(rg|te)|vk(40|5[0-3]|\-v)|vm40|voda|vulc|vx(52|53|60|61|70|80|81|83|85|98)|w3c(\-| )|webc|whit|wi(g |nc|nw)|wmlb|wonu|x700|xda(\-|2|g)|yas\-|your|zeto|zte\-/i.test(a.substr(0,4)))window.location=b})(navigator.userAgent||navigator.vendor||window.opera,'%(redirect_to)s');"
        script = base_script % {'redirect_to': request.build_absolute_uri(reverse(station_page, kwargs={'subdomain_name': subdomain_name}))}
        response = HttpResponse(script, mimetype='text/javascript')
        response['Content-Disposition'] = 'attachment; station_mobile_redirect.js'

    except Station.DoesNotExist:
        response = HttpResponseNotFound()

    return response

@work_station_required
def connection_check_failed(request, work_station):
    logging.info("connection check failed for workstation: %s" % work_station)
    msg = u"""
    Workstation didn't respond to to a connection check:
    \t%s
    """ % work_station

    notify_by_email(u"Connection check failed", msg=msg)
    return HttpResponse("OK")

@work_station_required
def connection_check_passed(request, work_station):
    logging.info("connection check passed for workstation: %s" % work_station)
    msg = u"""
    Workstation responded to to a connection check:
    \t%s
    """ % work_station

    notify_by_email(u"Connection check passed", msg=msg)
    return HttpResponse("OK")

def campaign_handler(request, campaign_id):
    logging.info("campaign_handler with id: %s" % campaign_id)
    ga_track_event(request, "campaign", campaign_id)
    if campaign_id == "tlv_taxi_mobile":
        return HttpResponseRedirect("http://tlv.taxiapp.co.il")

    return HttpResponseRedirect("/")


# -- utility functions --
def get_station_domain(request):
    host = request.META.get("SERVER_NAME", None)
    for domain in STATION_DOMAINS:
        if host.endswith(domain):
            return host.replace('www.', '').split(".")[0].lower()

    return None

def _send_order_with_version(orders):
    """
    Add version information and send orders to client

    @param orders: a list of order objects to send
    @return: a JSONResponse
    """
    return JSONResponse({"orders": orders,
                         "version": get_current_version()
    })
