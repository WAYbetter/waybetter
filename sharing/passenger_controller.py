# This Python file uses the following encoding: utf-8
import hashlib
from analytics.models import BIEvent, BIEventType
from billing.billing_manager import   get_token_url
from common.decorators import   force_lang
from common.geocode import geocode
from common.models import City, Country
from common.tz_support import      default_tz_now
from common.util import DAY_DELTA, notify_by_email, get_international_phone, generate_random_token, custom_render_to_response, ga_track_event
from django.conf import settings
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect, HttpResponseForbidden
from django.shortcuts import  get_object_or_404
from django.template.context import  Context
from django.template.context import RequestContext
from django.template.loader import get_template
from django.utils import translation, simplejson
from django.utils.translation import ugettext as _
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import csrf_exempt
from djangotoolbox.http import JSONResponse
from geo.coder import  get_shortest_duration
from notification.api import notify_passenger
from ordering import passenger_controller as ordering_passenger_controller
from ordering.decorators import  passenger_required_no_redirect
from ordering.forms import  CredentialsForm
from ordering.models import   Passenger, OrderType, SHARING_TIME_FACTOR, CURRENT_ORDER_KEY, CURRENT_PASSENGER_KEY, SHARING_TIME_MINUTES, CURRENT_BOOKING_DATA_KEY
from ordering.passenger_controller import SESSION_VERIFICATION_KEY, get_position_for_order
from ordering.util import  safe_delete_user, create_user, create_passenger, get_name_parts, update_user_details
from ordering.errors import UpdateUserError
from sharing.content_controller import get_sharing_cities_data
from sharing.forms import UserRegistrationForm
import logging

# these should match the fields of utils.Address._fields
HIDDEN_FIELDS = ["city", "street_address", "house_number", "country", "geohash", "lon", "lat"]

@cache_control(max_age=DAY_DELTA)
def resolve_structured_address(request):
    city = get_object_or_404(City, id=request.GET.get("city_id"))
    street = request.GET.get("street", "")
    house_number = request.GET.get("house_number", "")

    address = "%s %s, %s" % (street.strip(), house_number.strip(), city.name)
    geocoding_results = geocode(address, resolve_to_ids=True)

    errors = None
    if not geocoding_results:
        # try replacing house number
        address = "%s %s, %s" % (street.strip(), 1, city.name)
        geocoding_results = geocode(address, resolve_to_ids=True)
        if geocoding_results:
            errors = {"house_number": _("Not found")}
        else:
            errors = {"street": _("Not found"), "house_number": _("Not found")}

    return JSONResponse({'geocoding_results': geocoding_results, 'errors': errors})


def startup_message(request):
    res = { 'show_message': False }

    user_agent_lower = request.META.get("HTTP_USER_AGENT", "").lower()

    if True: #TODO_WB: Add actual check here
        t = get_template("mobile/startup_message.html")
#        t = get_template("mobile/suggest_apps.html")
        res['show_message'] = True
        c = RequestContext(request, {
            'is_android': user_agent_lower.find("android") > -1,
            'is_ios': user_agent_lower.find("iphone") > -1
        })
        res['page'] = t.render(c)

    return JSONResponse(res)

def passenger_home(request):
    request.session[CURRENT_ORDER_KEY] = None

    page_specific_class = "wb_home"
    hidden_fields = HIDDEN_FIELDS

    sharing_time_factor = SHARING_TIME_FACTOR
    sharing_time_minutes = SHARING_TIME_MINUTES
    sharing_constraint = "minutes"

    order_types = simplejson.dumps({'private': OrderType.PRIVATE,
                                    'shared': OrderType.SHARED})

    country_code = settings.DEFAULT_COUNTRY_CODE
    cities = None
    if not request.mobile:
        cities = get_sharing_cities_data()

    return custom_render_to_response('wb_home.html', locals(), context_instance=RequestContext(request))


def pg_home(request):
    request.mobile = True
    request.session[CURRENT_ORDER_KEY] = None

    page_specific_class = "wb_home"
    hidden_fields = HIDDEN_FIELDS

    order_types = simplejson.dumps({'private': OrderType.PRIVATE,
                                    'shared': OrderType.SHARED})

    country_code = settings.DEFAULT_COUNTRY_CODE

    cities = [{'id': city.id, 'name': city.name} for city in City.objects.filter(name="תל אביב יפו")]
 #    cities = [{'id': city.id, 'name': city.name} for city in City.objects.filter(name__in=["תל אביב יפו", "אריאל"])]

#    return render_to_response('wb_home.html', locals(), context_instance=RequestContext(request))
    return custom_render_to_response('wb_home_phonegap.html', locals(), context_instance=RequestContext(request))


@login_required
def user_profile(request):
    page_specific_class = "user_profile"
    user = request.user
    phone_formatted = _("Not Entered")
    bi_formatted = _("Not Entered")

    if request.method == "POST":
        new_email = request.POST.get("email", "").strip() or None
        new_first_name, new_last_name = get_name_parts(request.POST.get("fullname") or None)
        try:
            user = update_user_details(user, first_name=new_first_name, last_name=new_last_name, email=new_email)
        except UpdateUserError, e:
            error = e.message

    passenger = Passenger.from_request(request)
    if passenger:
        phone_formatted = passenger.phone
        profile_picture_url = passenger.picture_url
        if hasattr(passenger, "billing_info"):
            bi = passenger.billing_info
            card_formatted = "%s%s" % ("**** " * 4, bi.card_repr[-4:])
            exp_formatted = bi.expiration_date.strftime("%m/%y")
            bi_formatted = "%s %s: %s" % (card_formatted, _("Exp"), exp_formatted)

    user_data = [
            {'name': "fullname", 'label': _("Full Name"), 'value': user.get_full_name},
            {'name': "email", 'label': _("Email Address"), 'value': user.email},
            {'name': "mobile", 'label': _("Mobile Phone"), 'value': phone_formatted},
            {'name': "billing", 'label': _("Billing Info"), 'value': bi_formatted},
    ]

    return custom_render_to_response("user_profile.html", locals(), context_instance=RequestContext(request))


def verify_passenger(request):
    if request.method == "POST":
        local_phone = request.POST.get('local_phone')
        country = get_object_or_404(Country, code=request.POST.get('country_code', ""))
        verification_code = int(request.POST.get('verification_code', -1))

        response, passenger = validate_passenger_phone(request, local_phone, country, verification_code)
        return response

    else:
        country_code = settings.DEFAULT_COUNTRY_CODE
        return custom_render_to_response("verify_passenger.html", locals(), context_instance=RequestContext(request))


@passenger_required_no_redirect
def change_credentials(request, passenger):
    user = passenger.user
    if not user: # no user, can't change credentials
        return HttpResponseRedirect(reverse(registration))

    if request.method == "POST":
        form = CredentialsForm(user, data=request.POST)
        if form.is_valid():
            user = form.save()
            user = authenticate(username=user.username, password=form.cleaned_data['new_password1'])
            login(request, user)

            redirect_url = settings.CLOSE_CHILD_BROWSER_URI if request.mobile else reverse('wb_home')
            return HttpResponseRedirect(redirect_url)

    else: # GET
        form = CredentialsForm(user, initial={'email': user.email})

    return custom_render_to_response("change_credentials.html", locals(), context_instance=RequestContext(request))


@csrf_exempt
def book_ride(request):
    #TODO_WB: deprecated - remove once support for 1.1 is ended
    request.session[CURRENT_ORDER_KEY] = None
    result = {"status"      : "failed",
              "redirect"    : reverse("wb_home"),
              "action"      : "",
              "message"     : _("We have encountered an error. Please try again.") }


    result["message"] = u"כדי להנות משירות WAYbetter יש לעדכן את האפליקציה שברשותכם"
    return JSONResponse(result)

def send_ride_notifications(ride):
    ride_orders = ride.orders.all()
    for order in ride_orders:
        notify_passenger(order.passenger, get_order_msg(ride, order), force_sms=True)

@csrf_exempt
def passenger_login(request):
    user = authenticate(username=request.POST.get('username'), password=request.POST.get('password'))
    res = { 'success' : False }
    if user:
        try:
            passenger = user.passenger
        except Passenger.DoesNotExist:
            passenger = None

        if passenger:
            res = {'success': True, 'token': passenger.login_token, 'username': user.username}


    return JSONResponse(res)

def registration(request, step="auth"):
    country_code = settings.DEFAULT_COUNTRY_CODE
    page_specific_class = "registration"
    login_controller_url = reverse("mobile_auth_login") if request.mobile else reverse("auth_login")

    BIEvent.log(BIEventType.REGISTRATION_START, request=request)

    login_link = "%s?next=%s" % (login_controller_url, reverse(post_login_redirect))
    form = UserRegistrationForm()

    ga_track_event(request, "registration", "register_now", "after_ordering" if request.session.get(CURRENT_BOOKING_DATA_KEY) else "direct")

    if request.user.is_authenticated() and step == "auth":
        return post_login_redirect(request)

    return custom_render_to_response("passenger_registration.html", locals(), context_instance=RequestContext(request))


@login_required
def post_login_redirect(request):
    url = reverse("wb_home")

    passenger = Passenger.from_request(request)
    if not passenger:
        url = reverse(registration, kwargs={'step': 'phone'})

    elif not hasattr(passenger, "billing_info"):
        url = get_token_url(request)  # go to billing registration

    elif request.session.get(CURRENT_BOOKING_DATA_KEY):
        # continue booking process, mobile continues by closing child browser
        if request.mobile:
            url = reverse("wb_home")
        else:
            url = reverse("booking_continued")

    return HttpResponseRedirect(url)


def do_register_user(request):
    form = UserRegistrationForm(data=request.POST)
    if form.is_valid():
        email = form.cleaned_data["email"]
        password = form.cleaned_data["password"]

        first_name, last_name = get_name_parts(form.cleaned_data["name"])

        user = create_user(email, password, email, first_name, last_name)

        user = authenticate(username=user.username, password=form.cleaned_data["password"])
        login(request, user)

        # redirect to passenger step
        return JSONResponse({"redirect": reverse(post_login_redirect)})
    else:
        errors = [{'field_name': e, 'errors_ul': str(form.errors[e])} for e in form.errors.keys()]
        return JSONResponse({"errors": errors})


def do_register_passenger(request):
    """
    A one stop shop for handling registration of a new phone number, generationg a login token and updating the session.

    We make sure the request is made by an authenticated user. In case of validating:
        1. Existing phone number (existing passenger)
            If request.user is already a passenger, merge request.user.passenger into the existing passenger.
            Connect the (merged) existing passenger to request.user and delete any previous passenger.user.
        2. New phone number (new passenger)
            If request.user is already a passenger change his phone number.
            Otherwise, create a new passenger connected to request.user.
    """
    if not request.user.is_authenticated():
        return HttpResponseForbidden(_("You must be logged in to validate your phone."))

    local_phone = request.POST.get('local_phone')
    country = Country.objects.get(code=settings.DEFAULT_COUNTRY_CODE)
    verification_code = int(request.POST.get('verification_code', -1))

    response, passenger = validate_passenger_phone(request, local_phone, country, verification_code)
    if response.status_code != 200: # verification failed
        return response

    if passenger: # existing passenger
        try:
            user_passenger = request.user.passenger
        except Passenger.DoesNotExist:
            user_passenger = None

        if user_passenger and passenger != user_passenger:
            #TODO_WB: merge passengers
            notify_by_email("Merge Passengers Required", u"request.user.passenger:%s\nvalidated passenger:%s" % (request.user.passenger, passenger))
            return HttpResponseBadRequest(_("We are sorry but your phone cannot be changed now. We will contact you to resolve this issue as soon as possible"))

        # request.user should be is_authenticated if we get here
        if passenger.user and passenger.user != request.user:
            safe_delete_user(passenger.user, remove_from_db=True)

        passenger.user = request.user

    else: # new passenger
        try:
            # user is already a passenger, change phone
            passenger = request.user.passenger
            passenger.phone = local_phone
        except Passenger.DoesNotExist:
            # user is not a passenger, create new
            passenger = create_passenger(request.user, country, local_phone, save=False)

#    request.session[CURRENT_PASSENGER_KEY] = passenger
    passenger.login_token = hashlib.sha1(generate_random_token(length=40)).hexdigest()
    passenger.save()

    request.session[CURRENT_PASSENGER_KEY] = passenger

    return JSONResponse({"redirect": reverse(post_login_redirect)})


@csrf_exempt
def send_sms_verification(request):
    return ordering_passenger_controller.send_sms_verification(request)


def validate_passenger_phone(request, local_phone, country, verification_code):
    """
    Validate a passenger by phone and verification code.
    Return a response and the passenger (if exists) and save the passenger to the session.
    """
    response = HttpResponse("OK")
    passenger = None

    intl_phone_number = get_international_phone(country, local_phone)
    stored_code, stored_phone = request.session.get(SESSION_VERIFICATION_KEY, (None, None))

    if not (stored_code and stored_phone):
        response = HttpResponseBadRequest(_("Error validating phone (check that your browser accepts cookies)"))
    elif intl_phone_number != stored_phone or verification_code != int(stored_code):
        response = HttpResponseBadRequest(_("Invalid verification code"))
    else:
        try:
            passenger = Passenger.objects.get(phone=local_phone, country=country)
        except Passenger.DoesNotExist:
            pass
        except Passenger.MultipleObjectsReturned:
            msg = "Phone registered to multiple passengers: %s" % local_phone
            logging.error(msg)
            notify_by_email(msg)
            response =  HttpResponseBadRequest(_("We're sorry but your phone appears to used by multiple users. Please contact support@waybetter.com to resolve this issue."))

    request.session[CURRENT_PASSENGER_KEY] = passenger

    return response, passenger


# utility functions
def get_duration_to_point(ride, point):
    assert point.ride == ride
    result = 0
    ride_points = ride.points.all()
    for i, p in enumerate(ride_points):
        if i > 0:
            prev_p = ride_points[i-1]
            result += get_shortest_duration(prev_p.lat, prev_p.lon, p.lat, p.lon)

        if p == point:
            break

    logging.info("[get_duration_to_point] result = '%s'" % result)
    return result

def get_order_msg(ride, order):
    t = get_template("passenger_notification_msg.html")
    pickup_time = None
    position = get_position_for_order(order)
    if position:
        logging.info("use actual position for pickup estimate")
        duration = get_shortest_duration(position.lat, position.lon, order.from_lat, order.from_lon, sensor=True)
        logging.info("[get_order_msg] duration = '%s'" % duration)

        if duration:
            pickup_time = duration / 60

    if not pickup_time:
        if ride.pickup_estimate: # this is an estimate from the station
            duration = get_duration_to_point(ride, order.pickup_point)
            pickup_time = (duration / 60) + ride.pickup_estimate
        else: # no estimate given, use algo values
            if order.pickup_point.stop_time > default_tz_now():
                td = order.pickup_point.stop_time - default_tz_now()
                pickup_time = td.seconds / 60
            else:
                pickup_time = 1 # 'now'

    current_lang = translation.get_language()

    translation.activate(order.language_code)
    template_data = {'pickup_time': pickup_time,
                     'station_name': ride.station.name,
                     'taxi_number': ride.taxi_number
                     }

    msg = t.render(Context(template_data))
    translation.activate(current_lang)

    logging.info(u"order message %s" % msg)

    return msg

def get_passenger_ride_email(order):
    t = get_template("passenger_ride_email.html")

    template_data = {
        "order_id"          : order.id,
        "pickup"            : order.from_raw,
        "dropoff"           : order.to_raw,
        "num_seats"         : order.num_seats,
        "order_type"        : _("WAYbetter ride") if order.type == OrderType.SHARED else _("Private ride"),
        "price"             : order.get_billing_amount(),
        "depart_time"       : order.depart_time,
        "passenger_name"    : order.passenger.name
    }

    langcode_render = force_lang(order.language_code)(t.render)
    msg = langcode_render(Context(template_data))
    logging.info(msg)
    return msg