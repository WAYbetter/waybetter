# -*- coding: utf-8 -*-

# Create your views here.
from datetime import timedelta
from urllib import urlencode
from common.decorators import allow_JSONP, catch_view_exceptions
from google.appengine.api import channel, memcache
from common.geo_calculations import distance_between_points
from common.geocode import reverse_geocode, geocode, DEFAULT_RESULT_MAX_SIZE, get_city_from_location, geohash_encode
from common.models import Country, City
from common.route import calculate_time_and_distance
from common.sms_notification import send_sms
from common.tz_support import utc_now, default_tz_now, to_js_date
from common.util import gen_verification_code, log_event, EventType, get_international_phone, custom_render_to_response, blob_to_image_tag, YEAR_DELTA, DAY_DELTA, MINUTE_DELTA, get_channel_key, generate_random_token, notify_by_email, safe_fetch, get_mobile_platform
from django.conf import settings
from django.contrib.auth import login, authenticate
from django.contrib.auth.models import User
from django.contrib.admin.views.decorators import staff_member_required
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render_to_response
from django.template.context import RequestContext
from django.utils import simplejson
from django.utils.translation import ugettext as _, get_language_from_request
from django.views.decorators.cache import cache_control, never_cache
from django.views.decorators.csrf import csrf_exempt
from djangotoolbox.http import JSONResponse
from fleet.fleet_manager import  get_ride_position
from fleet.models import TaxiRidePosition, FleetManagerRideStatus
from notification.api import deregister_push_token
from ordering.decorators import passenger_required, passenger_required_no_redirect, NOT_A_USER, NOT_A_PASSENGER
from ordering.forms import OrderForm, HIDDEN_FIELDS, get_profile_form, BusinessRegistrationForm
from ordering import models
from ordering.models import Passenger, Business, Order, RATING_CHOICES, Station, PASSENGER_TOKEN, CURRENT_PASSENGER_KEY, WorkStation, PENDING, ACCEPTED, Device, InstalledApp, PickMeAppRide, SharedRide
from ordering.order_history import get_orders_history, ORDER_HISTORY_COLUMNS, ORDER_HISTORY_COLUMN_NAMES, ORDER_HISTORY_FIELDS, BUSINESS_ORDER_HISTORY_COLUMNS, BUSINESS_ORDER_HISTORY_COLUMN_NAMES, BUSINESS_ORDER_HISTORY_FIELDS
from ordering.pricing import estimate_cost, CostType
from ordering.util import create_user, create_passenger, safe_delete_user
from ordering.signals import order_created_signal
from interests.models import BusinessInterest, PilotInterest, M2MInterest
from interests.forms import BusinessInterestForm
from interests.views import interest_view
from testing.selenium_helper import SELENIUM_TEST_KEY, SELENIUM_VERIFICATION_CODE
import order_manager
import order_tracker
import logging
import re
import hashlib

TOKEN_SALT = "***REMOVED***"
ADDRESS_PARAMETER = "term"
MAX_SIZE_PARAMETER = "max_size"
ORDERING_INTERVAL = 60 # seconds
BUSINESS_ORDERING_INTERVAL = 5 # seconds
SESSION_VERIFICATION_KEY = "verification_code"
ESTIMATION_FUZZINESS_FACTOR = 0.2

def passenger_home(request):
    if not request.mobile and CURRENT_PASSENGER_KEY in request.session:
        del request.session[CURRENT_PASSENGER_KEY]

    hidden_fields = HIDDEN_FIELDS
    form = OrderForm()
    not_a_user, not_a_passenger = NOT_A_USER, NOT_A_PASSENGER
    waze_token = settings.WAZE_API_TOKEN
    telmap_user = settings.TELMAP_API_USER
    telmap_password = settings.TELMAP_API_PASSWORD
    telmap_languages = 'he' if str(get_language_from_request(request)) == 'he' else 'en'
    country_code = settings.DEFAULT_COUNTRY_CODE
    service_cities = ", ".join(set([s.city.name for s in Station.objects.filter(show_on_list=True)]))
    passenger = Passenger.from_request(request)

    if not passenger and request.GET.get("show_login", False):
        show_login = True

    if passenger and passenger.business:
        PENDING = models.PENDING
        ASSIGNED = models.ASSIGNED
        ACCEPTED = models.ACCEPTED
        ORDER_FAILED = models.FAILED # groups together FAILED, ERROR and TIMED_OUT
        ORDER_MAX_WAIT_TIME = models.ORDER_MAX_WAIT_TIME
        FAILED_MSG = _(order_tracker.STATUS_MESSAGES[models.FAILED])

        show_tracker = True
        channel_key = get_channel_key(Passenger.from_request(request), request.session.session_key)
        init_token = channel.create_channel(channel_key)
        init_tracker_history = [simplejson.dumps(msg) for msg in order_tracker.get_tracker_history(passenger)]

    return custom_render_to_response("passenger_home.html", locals(), context_instance=RequestContext(request))

def pickmeapp_home(request):
    if request.META.get('HTTP_USER_AGENT', "").lower().find("iphone") != -1: # this request came from an iphone
        logging.info("Redirecting iphone user to appstore   ")
        return HttpResponseRedirect("http://itunes.apple.com/il/app/pickmeapp/id444681703?mt=8&uo=4")

    return passenger_home(request)

def get_tracker_init(request):
    response = ''
    passenger = Passenger.from_request(request)
    if passenger:
        channel_key = get_channel_key(passenger, request.session.session_key)
        token = channel.create_channel(channel_key)
        tracker_history = order_tracker.get_tracker_history(passenger)

        response = {'tracker_history': tracker_history,
                    'token': token}

    return JSONResponse(response)


def info_pages(request):
    return custom_render_to_response("info.html", locals(), context_instance=RequestContext(request))


def fix_address(address, lon, lat):
    result = address.strip()

    parts = re.split("\s*[ ,]+\s*", result)
    no_city_entered = bool(len(parts) == 2 and (parts[0].isdigit() or parts[1].isdigit()))

    if lon and lat and no_city_entered:
        gps_city = get_city_from_location(lon, lat)
        result = u"%s %s" % (result, gps_city)

    return result


@cache_control(max_age=DAY_DELTA)
def resolve_address(request):
# get parameters
    if not ADDRESS_PARAMETER in request.GET:
        return HttpResponseBadRequest("Missing address")

    address = request.GET[ADDRESS_PARAMETER]
    lon = request.GET.get("lon", None)
    lat = request.GET.get("lat", None)
    include_order_history = request.GET.get("include_order_history", True)
    fixed_address = fix_address(address, lon, lat)

    size = request.GET.get(MAX_SIZE_PARAMETER) or DEFAULT_RESULT_MAX_SIZE
    try:
        size = int(size)
    except:
        return HttpResponseBadRequest("Invalid value for max_size")

    geocoding_results = geocode(fixed_address, max_size=size, resolve_to_ids=True)
    history_results = []
    if include_order_history:
        passenger = Passenger.from_request(request)
        if passenger:
            history_results.extend(
                [get_results_from_order(o, "from") for o in passenger.orders.filter(from_raw__icontains=address)])
            history_results.extend(
                [get_results_from_order(o, "to") for o in passenger.orders.filter(to_raw__icontains=address)])
            history_results_by_name = {}
            for result in history_results:
                history_results_by_name[result["name"]] = result

            history_results = history_results_by_name.values()

            # remove duplicate results
            history_results_names = [result_name for result_name in history_results_by_name]

            for result in geocoding_results:
                if result['name'] in history_results_names:
                    geocoding_results.remove(result)

    return JSONResponse({"geocode": geocoding_results[:size],
                         "history": history_results[:size],
                         "geocode_label": "map_suggestion",
                         "history_label": "history_suggestion"
    })


@cache_control(max_age=YEAR_DELTA)
@allow_JSONP
def resolve_coordinates(request):
    lon = request.GET.get('lon', -1)
    lat = request.GET.get('lat', -1)
    if lon == -1 or lat == -1:
        return HttpResponseBadRequest('Invalid arguments')

    result = reverse_geocode(float(lat), float(lon))

    return JSONResponse(result)


def get_results_from_order(order, field_prefix):
    city = getattr(order, field_prefix + "_city")
    country = getattr(order, field_prefix + "_country")
    return {
        "lat": getattr(order, field_prefix + "_lat"),
        "lon": getattr(order, field_prefix + "_lon"),
        "name": getattr(order, field_prefix + "_raw"),
        "raw": getattr(order, field_prefix + "_raw"),
        "street_address": getattr(order, field_prefix + "_street_address"),
        "house_number": getattr(order, field_prefix + "_house_number") or 1,
        "city": city.id if city else None,
        "country": country.id if country else None,
        "geohash": getattr(order, field_prefix + "_geohash"),
        }


#@require_parameters(required_params=("from_lon", "from_lat", "to_lon", "to_lat"))
@cache_control(max_age=10 * MINUTE_DELTA)
def estimate_ride_cost(request):
    from_lon = request.GET["from_lon"]
    from_lat = request.GET["from_lat"]
    to_lon = request.GET["to_lon"]
    to_lat = request.GET["to_lat"]
    from_city = int(request.GET["from_city"])
    to_city = int(request.GET["to_city"])
    result = calculate_time_and_distance(from_lon, from_lat, to_lon, to_lat)
    estimated_duration, estimated_distance = result["estimated_duration"], result["estimated_distance"]
    cities = [from_city, to_city]
    if not (estimated_distance and estimated_duration):
        return JSONResponse({
            "estimated_cost": "",
            "estimated_duration": "",
            "currency": "",
            "label": _("Ride estimation not available")
        })
    ride_cost, ride_type = estimate_cost(estimated_duration, estimated_distance, cities=cities)

    if ride_type == CostType.METER:
        label = _('Estimated ride cost')
        cost = "%d-%d" % (ride_cost, ride_cost * (1 + ESTIMATION_FUZZINESS_FACTOR))
    elif ride_type == CostType.FLAT:
        label = _('Flat rate')
        cost = "%d" % ride_cost

    result = {
        "estimated_cost": cost,
        "estimated_duration": "%d-%d %s" % (estimated_duration / 60,
                                            estimated_duration * (1 + ESTIMATION_FUZZINESS_FACTOR) / 60, _('min')),
        "currency": u'₪', # TODO_WB: change to non hardcoded version
        "label": label
    }
    return JSONResponse(result)


@csrf_exempt
@catch_view_exceptions
@passenger_required_no_redirect
def book_order(request, passenger):
    def error_response(message):
        result = {
            "status": "error",
            "errors": {
                "title": _("Your Ride Could Not Be Ordered"),
                "message": message
            }}
        return JSONResponse(result)

    def _fix_missing_house_number(order, order_type):
        res = getattr(order, "%s_raw" % order_type)
        street = getattr(order, "%s_street_address" % order_type)
        try:
            city = getattr(order, "%s_city" % order_type).name
            res = res.replace(street, "").replace(city, "").replace(",", "").strip()
            res = int(res)
            logging.info("fixed house number (%s): %s " % (res, getattr(order, "%s_raw" % order_type)))
        except AttributeError, ValueError:
            logging.warning("Could not fix missing house number: %s" % getattr(order, "%s_raw" % order_type))
            res = None

        return res

    form_data = request.POST
    if passenger.business and request.POST.get("business_order"):
        form_data = get_business_order_form_data(request, passenger)

    form = OrderForm(data=form_data, passenger=passenger)

    if form.is_valid():
        if passenger.orders.all()[:1]:
            last_order = passenger.orders.order_by("-create_date")[0]
            interval = BUSINESS_ORDERING_INTERVAL if passenger.business else ORDERING_INTERVAL
            if (utc_now() - last_order.create_date).seconds < interval:
                return error_response(_("Ordering is not allowed so soon after another order"))

        app_udid = request.POST.get("APP_UDID")
        installed_app = None
        if app_udid: # this came from a device that sends app specific id
            installed_app = InstalledApp.by_app_udid(app_udid)
            if not installed_app:
                return error_response(_("Please register before attempting to order"))
            if installed_app.blocked:
                return error_response(_("Your account has been suspended. Please contact support@waybetter.com"))

        order = form.save(commit=False)
        order.language_code = request.POST.get("language_code", get_language_from_request(request))
        order.debug = settings.DEV
        order.passenger = passenger
        order.mobile = request.mobile
        order.user_agent = request.META.get("HTTP_USER_AGENT")
        order.installed_app = installed_app

        if not order.from_house_number:
            order.from_house_number = _fix_missing_house_number(order, "from")

        if order.to_raw and not order.to_house_number:
            order.to_house_number = _fix_missing_house_number(order, "to")

        station_unique_id = request.POST.get("station_unique_id")
        if station_unique_id:
            logging.info("station_unique_id submitted: %s" % station_unique_id)
            stations = Station.objects.filter(unique_id=station_unique_id)
            if stations:
                order.originating_station = stations[0]
                order.confining_station = stations[0]
            else:
                return error_response(_("Could not send order to specified station"))

        order.save()
        order_created_signal.send(sender="order_created_signal", obj=order)

        if passenger.phone != settings.APPLE_TESTER_PHONE_NUMBER:
            order_manager.book_order_async(order)
        else: # assign order to test station so the user will see it in his history
            order.station = Station.by_id(1713061)
            order.pickup_time = 5
            order.save()
            order.change_status(old_status=PENDING, new_status=ACCEPTED)

        log_event(EventType.ORDER_BOOKED, order=order)

        book_order_message = _('An SMS with ride details will arrive shortly...')
        if order.originating_station_id:
            book_order_message = _(
                "%s is looking for a free taxi. An SMS with ride details will arrive shortly...") % order.originating_station.name

        book_order_result = {
            "status": "booked",
            "message": book_order_message,
            "order_id": order.id,
            "tracker_msg": simplejson.dumps(order_tracker.get_tracker_msg_for_order(order)),
            "show_registration": 0 if order.passenger.user else 1        # signal the show registration dialog
        }
        return JSONResponse(book_order_result)

    else: # order form invalid
        logging.error("order form invalid: %s" % form.errors.items())
        message = u""
        for k, v in form.errors.items():
            if k == "__all__":
                message += u", ".join(v)
            else:
                message += u"%s: %s" % (k, v.as_pure_text())
            message += "\n"

        return error_response(message)



@passenger_required
def get_passenger_orders_history(request, passenger):
    if passenger.business:
        template_name = "business_orders_history.html"
        columns = BUSINESS_ORDER_HISTORY_COLUMNS
        names = BUSINESS_ORDER_HISTORY_COLUMN_NAMES
        fields = BUSINESS_ORDER_HISTORY_FIELDS
    else:
        is_popup = True
        template_name = "orders_history.html"
        rating_choices = simplejson.dumps([{"val": c[0], "name": c[1]} for c in RATING_CHOICES])
        columns = ORDER_HISTORY_COLUMNS
        names = ORDER_HISTORY_COLUMN_NAMES
        fields = ORDER_HISTORY_FIELDS

    order_history_columns = simplejson.dumps(columns)
    order_history_column_names = simplejson.dumps([unicode(s) for s in names])
    order_history_fields = simplejson.dumps(fields)
    history_data_url = reverse(get_passenger_orders_history_data)
    return custom_render_to_response(template_name, locals(), RequestContext(request))


@passenger_required_no_redirect
def get_passenger_orders_history_data(request, passenger):
    keywords = request.GET.get("keywords", None)
    page = int(request.GET.get("page", "1"))
    sort_by = request.GET.get("sort_by", "create_date")
    sort_dir = request.GET.get("sort_dir", "-")
    data = get_orders_history(passenger, page, keywords, sort_by, sort_dir)
    return JSONResponse(data)


@passenger_required_no_redirect
@cache_control(max_age=DAY_DELTA)
def get_order_address(request, passenger):
    order_id = request.GET.get("order_id")
    address_type = request.GET.get("address_type")
    order = get_object_or_404(Order, id=order_id, passenger=passenger)

    return JSONResponse(get_results_from_order(order, address_type))

def phone_activation(request):
    app_udid = request.GET.get("APP_UDID")
    phone = request.GET.get("phone")

    return custom_render_to_response("phone_activation.html", locals(), context_instance=RequestContext(request))

@csrf_exempt
def request_phone_activation(request):
    app_udid = request.POST.get("APP_UDID")
    phone = request.POST.get("phone")

    notify_by_email("Phone Activation Request: %s" % app_udid, "phone: %s, app_udid: %s" % (phone, app_udid))
    return HttpResponse("OK")


@csrf_exempt
def register_device(request):
    def report_conversion(udid):
        url = "http://tracking.taptica.com/aff_u"
        payload = urlencode({
            "tt_adv_id"     : 612,
            "tt_deviceid"   : udid,
            "tt_appid"      : 501682022,
            "tt_time"       : default_tz_now().strftime("%Y-%m-%d %H:%M:%S.%f"),
        })
        url = "%s?%s" % (url, payload)
        logging.info("report_conversion: %s" % url)
        res = safe_fetch(url, method="GET", deadline=15)
        if res:
            res = simplejson.loads(res.content)["tt_cid"]

        return res

    local_phone = request.POST.get("local_phone")
    udid = request.POST.get("UDID")
    gudid = request.POST.get("GUDID")
    app_udid = request.POST.get("APP_UDID")
    app_name = request.POST.get("application_name")

    installed_app = InstalledApp.by_app_udid(app_udid)
    device = Device.by_udid(udid)
    passenger_created = False

    cid = report_conversion(udid)
    if cid: logging.info("cid = %s" % cid)

    if installed_app and device:
        assert installed_app.device == device

    if not device:
        logging.info("creating device with udid=%s and gudid=%s" % (udid, gudid))
        device = Device(udid=udid, gudid=gudid)
        device.save()

    if not installed_app:
        logging.info("creating installed app with app_udid=%s" % app_udid)
        installed_app = InstalledApp(app_udid=app_udid,
                                     name=app_name,
                                     cid=cid,
                                     device=device,
                                     user_agent=request.META.get("HTTP_USER_AGENT"))
    else:
        logging.info("installed app exists, updating")
        installed_app.install_count += 1
        if cid: installed_app.cid = cid

    country = get_object_or_404(Country, code=request.POST.get('country_code', ""))
    passengers = Passenger.objects.filter(country=country, phone=local_phone)

    if passengers:
        passenger = passengers[0]
    else:
        passenger = create_passenger(None, country, local_phone, save=False)
        passenger.login_token = hashlib.sha1(generate_random_token(length=40)).hexdigest()
        passenger.save()
        passenger_created = True
        request.session[CURRENT_PASSENGER_KEY] = passenger

    if passenger_created:
        installed_app.passenger = passenger
        installed_app.user_agent = request.META.get("HTTP_USER_AGENT")

    installed_app.save()

    if local_phone == settings.APPLE_TESTER_PHONE_NUMBER:
        return JSONResponse({PASSENGER_TOKEN: passenger.login_token})

    if installed_app.passenger != passenger:
        return HttpResponseBadRequest(_("The phone number is already registered."))

    return JSONResponse({PASSENGER_TOKEN: passenger.login_token})

@csrf_exempt
def send_sms_verification(request):
    country_code = request.POST.get("country_code")
    local_phone = request.POST.get("local_phone")
    test_key = request.POST.get("test_key", None)

    if not local_phone:
        return HttpResponseBadRequest("missing phone parameter")

    country = get_object_or_404(Country, code=country_code)
    phone = get_international_phone(country, local_phone)

    if local_phone == settings.APPLE_TESTER_PHONE_NUMBER:
        code = str(set_session_sms_code(request, phone, code=settings.APPLE_TESTER_VERIFICATION))
    elif test_key == SELENIUM_TEST_KEY:
        code = str(set_session_sms_code(request, phone, code=SELENIUM_VERIFICATION_CODE))
    else:
        code = str(set_session_sms_code(request, phone))
        send_sms(local_phone, _("Verification code: %s") % code)

    logging.info("Sending SMS verification code: %s" % code)
    return HttpResponse("OK")


@csrf_exempt
def validate_phone(request):
    local_phone = request.POST.get('local_phone')
    verification_code = int(request.POST.get('verification_code', -1))
    country = get_object_or_404(Country, code=request.POST.get('country_code', ""))
    stored_code, stored_phone = request.session.get(SESSION_VERIFICATION_KEY, (None, None))
    intl_phone_number = get_international_phone(country, local_phone)

    if not (stored_code and stored_phone):
        return HttpResponseBadRequest(_("Error validating phone (check that your browser accepts cookies)"))

    if intl_phone_number != stored_phone or verification_code != int(stored_code):
        return HttpResponseBadRequest(_("Invalid verification code"))

    # there is a user
    if request.user.is_authenticated():
        #TODO_WB: check if user already has a passenger
        try:
            # has a passenger? update phone
            passenger = Passenger.objects.get(user=request.user)
            passenger.phone = local_phone
            passenger.phone_verified = True
            passenger.save()
            return HttpResponse(local_phone)

        except Passenger.DoesNotExist:
            # create passenger
            passenger = create_passenger(None, country, local_phone)
            passenger.user = request.user
            passenger.save()

    # no user, get a passenger
    else:
        try:
            passenger = Passenger.objects.filter(country=country).filter(phone=local_phone).get()
        except Passenger.DoesNotExist:
            passenger = create_passenger(None, country, local_phone)
        except Passenger.MultipleObjectsReturned:
            return HttpResponseBadRequest(
                _("Phone has multiple passengers")) # shouldn't happen to real passengers (only staff)

        request.session[CURRENT_PASSENGER_KEY] = passenger

    # reset login token after validation
    # TODO_WB: check if login_token exists
    # TODO_WB: add phone number to salt the token

    passenger.login_token = hashlib.sha1(generate_random_token(length=40)).hexdigest()
    passenger.save()

    return JSONResponse({PASSENGER_TOKEN: passenger.login_token})


@csrf_exempt
def login_passenger(request):
    username = request.POST.get('username')
    password = request.POST.get('password')
    user = authenticate(username=username, password=password)

    if user:
        login(request, user)
        # if this is a passenger update the session list
        try:
            passenger = user.passenger
            passenger.cleanup_session_keys()
            passenger.session_keys.append(request.session.session_key)
            passenger.save()
        except Passenger.DoesNotExist:
            pass
        return HttpResponse("OK")
    else:
        return HttpResponseForbidden(_("wrong email/password"))


#@require_parameters(method='POST', required_params=('password',))
@passenger_required_no_redirect
def change_credentials(request, passenger):
    user = passenger.user

    if not user:
        return HttpResponseBadRequest(_("Must have a user to change credentials"))

    new_password = request.POST.get('password', None)
    new_email = request.POST.get('email', None)

    if new_email and new_email != user.email:
        passenger.user = create_user(new_email, new_password, new_email)
        passenger.save()
        safe_delete_user(user, remove_from_db=True)
        new_user = authenticate(username=new_email, password=new_password)
    else:
        user.set_password(new_password)
        user.save()
        new_user = authenticate(username=user.username, password=new_password)

    login(request, new_user)

    return HttpResponse("OK")


#@require_parameters(method='POST', required_params=('email', 'password'))
@passenger_required_no_redirect
def register_passenger(request, passenger):
    username = request.POST.get('email')
    password = request.POST.get('password')
    email = request.POST.get('email')
    approve_emails = request.POST.get('approve_emails')

    if User.objects.filter(email=email).count():
        return HttpResponseBadRequest(_("Email already registered"))

    user = create_user(username, password, email)

    user = authenticate(username=username, password=password)
    login(request, user)

    passenger.user = user
    if not approve_emails:
        passenger.accept_mailing = False
    passenger.save()

    return HttpResponse("OK")


@passenger_required
def edit_profile(request, passenger):
    form = get_profile_form(passenger, request.POST)
    if form.is_valid():
        save_user = False
        save_passenger = False

        # update user
        user = passenger.user

        if "first_name" in form.cleaned_data and user.first_name != form.cleaned_data["first_name"]:
            user.first_name = form.cleaned_data["first_name"]
            save_user = True

        if "last_name" in form.cleaned_data and user.last_name != form.cleaned_data["last_name"]:
            user.last_name = form.cleaned_data["last_name"]
            save_user = True

        if "password" in form.cleaned_data and len(form.cleaned_data["password"]) > 0:
            user.set_password(form.cleaned_data["password"])
            save_user = True

        if save_user: user.save()

        # update passenger
        for field in [f.name for f in Passenger._meta.fields]:
            if field in form.cleaned_data:
                if getattr(passenger, field) != form.cleaned_data[field]:
                    setattr(passenger, field, form.cleaned_data[field])
                    save_passenger = True

        if save_passenger: passenger.save()

        # update business
        if passenger.business:
            business = passenger.business
            save_business = False
            for field in [f.name for f in Business._meta.fields]:
                if field in form.cleaned_data:
                    if getattr(business, field) != form.cleaned_data[field]:
                        setattr(business, field, form.cleaned_data[field])
                        save_business = True

            if save_business: business.save()

        return HttpResponse("")


@passenger_required
def profile_page(request, passenger):
    if SESSION_VERIFICATION_KEY in request.session:
        del(request.session[SESSION_VERIFICATION_KEY])

    is_popup = True
    #    form_data = {'country': passenger.country.id}
    form_data = {}

    if passenger.default_station:
        form_data.update({'default_station': passenger.default_station.id})

    if passenger.user.first_name:
        form_data.update({'first_name': passenger.user.first_name})

    if passenger.user.last_name:
        form_data.update({'last_name': passenger.user.last_name})

    if passenger.business:
        name = passenger.business.name
        username = passenger.user.username
        address = passenger.business.address
        form_data.update({'confine_orders': passenger.business.confine_orders})
        form_data.update({'contact_person': passenger.business.contact_person})
        form_data.update({'phone': passenger.phone})
        form_data.update({'email': passenger.user.email})

    form = get_profile_form(passenger, form_data)
    context = locals()
    context.update({'phone': passenger.phone,
                    'email': passenger.user.email})

    return custom_render_to_response("passenger_profile.html", context, context_instance=RequestContext(request))


def check_phone_registered(request):
    local_phone = request.GET.get("local_phone")
    return JSONResponse(local_phone and is_phone_registered(local_phone))


def check_phone_not_registered(request):
    local_phone = request.GET.get("local_phone")
    return JSONResponse(local_phone and not is_phone_registered(local_phone))


def stations_tab(request):
    stations_data = []
    for station in Station.objects.filter(show_on_list=True):
        stations_data.append({
            "name": station.name,
            "description": station.description,
            "phones": u"|".join([p.local_phone for p in station.phones.all()]),
            "website": station.website_url,
            "address": u"%s, %s" % (station.address, station.city.name),
            "logo": blob_to_image_tag(station.logo),
            "station_page_url": station.get_station_page_link() if station.subdomain_name else ""
            })

    return custom_render_to_response("stations.html", locals(), context_instance=RequestContext(request))


@passenger_required_no_redirect
@never_cache
def get_stations(request, passenger):
    result = {}
    stations = Station.objects.filter(show_on_list=True)
    for station in stations:
        city_name = station.city.name

        data = { "name":             station.name,
                 "id":               station.id,
                 "favorite_station": bool(passenger.default_station == station) }

        if city_name in result:
            result[city_name].append(data)
        else:
            result[city_name] = [data]

    return JSONResponse(result)


@csrf_exempt
@passenger_required_no_redirect
def set_default_station(request, passenger):
    if not "station_id" in request.POST:
        return HttpResponseBadRequest("Missing required argument")

    station_id = request.POST.get("station_id", None)
    if station_id and station_id != "-1":
        station = get_object_or_404(Station, id=station_id)
    else:
        station = None

    passenger.default_station = station
    passenger.save()

    return HttpResponse("OK")


def business_tab(request):
    return interest_view(request, BusinessInterestForm, "business_tab.html")

@staff_member_required
def business_registration(request):
    if request.method == 'POST':
        form = BusinessRegistrationForm(request.POST)
        if form.is_valid():
            business = form.save()
            log_event(EventType.BUSINESS_REGISTERED, passenger=business.passenger)

            # send a welcoming email to the business
            business.send_welcome_email(form.cleaned_data["password"])
            response = {"business_created": True}

        else: # form invalid
            errors = [{e: form.errors.get(e)} for e in form.errors.keys()]
            response = {"errors": errors}

        return JSONResponse(response)

    else: # GET
        interest_id = request.GET.get('from_interest_id', None)
        if interest_id:
            interest = BusinessInterest.objects.get(id=int(interest_id))
            data = {"email": interest.email,
                    "contact_person": interest.contact_person,
                    "phone": interest.phone}

            if interest.from_station:
                data.update({"from_station": interest.from_station.id})
                from_station_name = interest.from_station.name

            form = BusinessRegistrationForm(initial=data)

        else:
            form = BusinessRegistrationForm()

        return custom_render_to_response("business_registration.html", locals(),
                                         context_instance=RequestContext(request))

def get_ws_online_count(request):
    online_ws_count = len(filter(lambda ws: ws.station.show_on_list, WorkStation.objects.filter(is_online=True)))
    return JSONResponse(online_ws_count)

def landing_page(request):
    if request.mobile:
        return passenger_home(request)

    return custom_render_to_response("landing_page.html", locals(), context_instance=RequestContext(request))

def pilot_interest(request):
    email = request.POST.get("email")
    location = request.POST.get("location")
    if email and location:
        interest = PilotInterest(email=email, location=location)
        interest.save()

    return HttpResponse("OK")

def m2m_interest(request):
    email = request.POST.get("email")
    if email:
        interest = M2MInterest(email=email)
        interest.save()

    return HttpResponse("OK")

def terms_for_station_app(request):
    res = HttpResponse()
    station_unique_id = request.GET.get("sid")
    if station_unique_id:
        station = Station.objects.filter(unique_id=station_unique_id)
        if station:
            res = render_to_response("station_terms/%s" % station[0].application_terms)

    return res


def track_order(request, order_id):
    order = Order.by_id(order_id)
    use_mock = False
    ride = None
    expiration_date = default_tz_now()
    if order:
        try:
            ride = order.ride or order.pickmeapp_ride
        except (SharedRide.DoesNotExist, PickMeAppRide.DoesNotExist):
            pass
    else:
        error_message = _("This ride is invalid")

    if not ride:
        error_message = _("This ride is invalid")
    else:
        expiration_date = ride.arrive_time + timedelta(minutes=15)
        if expiration_date < default_tz_now():
            error_message = _("This ride has expired")

    if ride.station:
        station_icon_url = ride.station.app_icon_url
        station_phone = ride.station.phone

    if request.GET.get("use_mock"):
        error_message = ""
        station_icon_url = "https://s3.amazonaws.com/stations_icons/ny_icon.png"
        use_mock = True
        expiration_date = default_tz_now() + timedelta(minutes=15)

    expiration_date = to_js_date(expiration_date)# prepare for JS consumption

    return custom_render_to_response('track_order.html', locals(), context_instance=RequestContext(request))

def get_order_position(request, order_id):
    """
    Return a taxi position and pickup/dropoff status for taxi tracking page.

    position : TaxiRidePosition if there is a position, None if there is no position or it is stale (expired)
    passenger_pickup_up: bool indicating if the passenger is on the taxi
    """
    order = Order.by_id(order_id)
    position = get_position_for_order(order)

    response = {
        'position': position.__dict__ if position else None,
        'passenger_picked_up': order.pickup_point.visited,
    }
    logging.info(response)
    return JSONResponse(response)


def get_position_for_order(order):
    """

    @return: None or a C{TaxiRidePosition}
    """
    position = None

    try:
        ride = order.ride or order.pickmeapp_ride
    except PickMeAppRide.DoesNotExist, e:
        logging.error("PickMeAppRide.DoesNotExist")
        ride = None

    if ride:
        position = get_ride_position(ride)
    else:
        logging.error("no ride found for order: %s" % order.id)


    # TODO_WB: check if position is not stale (expired).
    # problem is that position.timestamp can't be trusted - ISR sends wrong time
    return position

@csrf_exempt
def update_push_token(request):
    token = request.POST.get("push_token")
    old_token = request.POST.get("old_token")

    logging.info("update_push_token %s -> %s" % (old_token, token))
    passenger = Passenger.from_request(request)

    if passenger and passenger.push_token != token:
        if passenger.push_token:
            deregister_push_token(passenger)

        passenger.mobile_platform = get_mobile_platform(request.META.get('HTTP_USER_AGENT', ""))
        passenger.push_token = token
        passenger.save()

    return HttpResponse("OK")

# utility methods
def get_business_order_form_data(request, passenger):
    form_data = request.POST.copy()
    country_id = Country.objects.get(code=settings.DEFAULT_COUNTRY_CODE).id

    if passenger.default_station and passenger.business.confine_orders:
        form_data["confining_station"] = passenger.default_station.id

    form_data["taxi_is_for"] = request.POST.get("taxi_is_for", "")
    form_data["comments"] = request.POST.get("comments", "")

    def resolve_lat_lon_or_default(city, street_address, house_number):
        lat = -1
        lon = -1
        street_address = street_address.strip()
        house_number = house_number.strip()
        address = "%s %s, %s" % (street_address, house_number, city.name)
        geocoding_results = geocode(address, resolve_to_ids=True)
        for result in geocoding_results:
            # make sure it is a match and not a suggestion
            if result["street_address"] == street_address and result["house_number"] == house_number:
                lat = result["lat"]
                lon = result["lon"]
                break

        return lat, lon

    from_city = City.by_id(form_data.get("from_city"))
    from_hn = re.search("(\d+)", form_data.get("from_street_address", ""))
    from_hn = str(from_hn.groups()[0] if from_hn else "")
    from_street_address = form_data.get("from_street_address", "").replace(from_hn, "")
    from_lat, from_lon = resolve_lat_lon_or_default(from_city, from_street_address, from_hn)
    form_data.update({
        "from_country": country_id,
        "from_raw": "%s %s %s" % (from_street_address, from_hn, from_city.name),
        "from_street_address": from_street_address,
        "from_house_number": from_hn,
        "from_lat": from_lat,
        "from_lon": from_lon,
        "from_geohash": geohash_encode(from_lon, from_lat),
        })

    to_city = City.by_id(form_data.get("to_city"))
    if to_city:
        to_hn = re.search("(\d+)", form_data.get("to_street_address", ""))
        to_hn = str(to_hn.groups()[0] if to_hn else "")
        to_street_address = form_data.get("to_street_address", "").replace(to_hn, "")
        to_lat, to_lon = resolve_lat_lon_or_default(to_city, to_street_address, to_hn)
        form_data.update({
            "to_country": country_id,
            "to_raw": "%s %s %s" % (to_street_address, to_hn, to_city.name),
            "to_street_address": to_street_address,
            "to_house_number": to_hn,
            "to_lat": to_lat,
            "to_lon": to_lon,
            "to_geohash": geohash_encode(to_lon, to_lat)
        })

    return form_data


def set_session_sms_code(request, phone, code=None):
    # if code is given we set it as the code (useful when testing)
    if not code:
        code = gen_verification_code()

    request.session[SESSION_VERIFICATION_KEY] = (code, phone)

    return code


def is_phone_registered(local_phone):
    """
    checks if the given phone already registered (belongs to a registered user)
    """
    phone_registered = False

    passengers = Passenger.objects.filter(phone=local_phone).filter(country=Country.get_id_by_code("IL"))
    if passengers.count() > 0:
        try:
            user = passengers[0].user
        except User.DoesNotExist:
            user = None

        phone_registered = user is not None
    else:
        phone_registered = False

    return phone_registered
