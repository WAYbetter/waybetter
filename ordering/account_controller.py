import hashlib
import logging
from analytics.models import BIEvent, BIEventType
from billing.billing_manager import get_token_url
from common.models import Country
from common.util import generate_random_token, notify_by_email
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.core.validators import validate_email
from django.utils.translation import ugettext as _
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.http import HttpResponseNotAllowed, HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext
from djangotoolbox.http import JSONResponse
from ordering.errors import UpdateUserError
from ordering.models import Passenger, CURRENT_PASSENGER_KEY
from ordering.util import get_name_parts, create_user, create_passenger, update_user_details

def account_view(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect(reverse(registration_view))

    PASSWORD_MASK = "********"

    user = request.user
    passenger = user.passenger

    if request.method == 'GET':
        name = user.get_full_name()
        email = user.email
        password = PASSWORD_MASK
        phone = passenger.phone
        billing_info = passenger.billing_info.card_repr[-4:] if hasattr(passenger, "billing_info") else None

        title = _("Your Account")
        return render_to_response("mobile/account_registration.html", locals(), RequestContext(request))

    elif request.method == 'POST':
        new_email = request.POST.get("email", "").strip() or None
        new_first_name, new_last_name = get_name_parts(request.POST.get("name") or None)
        new_password = request.POST.get("password", "").replace(PASSWORD_MASK, "") or None
        new_phone = request.POST.get("phone", "") or None

        try:
            user = update_user_details(user, first_name=new_first_name, last_name=new_last_name, email=new_email, password=new_password, phone=new_phone)
            if new_password:
                user = authenticate(username=user.username, password=new_password)
                login(request, user)
        except UpdateUserError, e:
            return JSONResponse({'error': e.message})

        # success
        return JSONResponse({'redirect': reverse(account_view), 'billing_url': (get_token_url(request))})

    else:
        return HttpResponseNotAllowed(request.method)


def registration_view(request):
    if request.user.is_authenticated():
        return HttpResponseRedirect(reverse(account_view))

    if request.method == 'GET':
        BIEvent.log(BIEventType.REGISTRATION_START, request=request)

        title = _("Join WAYbetter")
        return render_to_response("mobile/account_registration.html", locals(), RequestContext(request))

    elif request.method == 'POST':
        email = request.POST.get("email")
        phone = request.POST.get("phone")

        try:
            validate_email(email)
        except ValidationError:
            return JSONResponse({'error': _("Invalid email")})

        # fail if email is registered
        if User.objects.filter(username=email).count() > 0:
            notify_by_email("Help! I can't register!", msg="email %s already registered\n%s" % (email, phone))
            return JSONResponse({'account_exists': True, 'error': _("This email address was registered by another user.")})

        # fail if phone is registered to more than 1 passenger
        country = Country.objects.get(code=settings.DEFAULT_COUNTRY_CODE)
        existing_passengers = Passenger.objects.filter(phone=phone, country=country)
        if len(existing_passengers) > 1:
            notify_by_email("Help! I can't register!", msg="phone %s registered to multiple passengers\n%s" % (phone, existing_passengers))
            return JSONResponse({'failed': True, 'error': _("This phone number is registered to multiple passengers. Please contact support for help.")})

        # fail if phone is registered to 1 passenger but this passenger has a user
        existing_passengers_users = [existing_passenger.user for existing_passenger in existing_passengers]
        if any(existing_passengers_users):
            notify_by_email("Help! I can't register!", msg="phone %s already registered to another user\n%s\n%s" % (phone, email, existing_passengers_users))
            return JSONResponse({'failed': True, 'error': _("This phone number was registered by another user. Please contact support for help.")})

        # by now we know:
        # 1. email is not registered; we will create a new user
        # 2. phone is not registered; we will create a new passenger
        #   OR
        # 3. phone registered to a passenger with NO user; we will keep the passenger and create a user for her
        passenger = existing_passengers[0] if existing_passengers else None
        user = register_new_user(request, passenger)
        if user:
            redirect = settings.CLOSE_CHILD_BROWSER_URI
            return JSONResponse({'redirect': redirect, 'billing_url': (get_token_url(request))})
        else:
            return JSONResponse({'error': _("Registration failed")})

    else:
        return HttpResponseNotAllowed(request.method)

def register_new_user(request, passenger=None):
    logging.info("registration %s" % request.POST)

    name = request.POST.get("name")
    email = request.POST.get("email")
    password = request.POST.get("password")
    phone = request.POST.get("phone")

    if not all([name, email, password, phone]):
        return None

    first_name, last_name = get_name_parts(name)
    user = create_user(email, password, email, first_name, last_name)
    user = authenticate(username=user.username, password=password)
    login(request, user)

    if passenger:
        passenger.user = user
    else:  # create a new one
        country = Country.objects.get(code=settings.DEFAULT_COUNTRY_CODE)
        passenger = create_passenger(request.user, country, phone, save=False)
        passenger.login_token = hashlib.sha1(generate_random_token(length=40)).hexdigest()

    passenger.save()

    request.session[CURRENT_PASSENGER_KEY] = passenger

    return user


def get_billing_url(request):
    return JSONResponse({'billing_url': (get_token_url(request))})


def apply_promo_code(request):
    return HttpResponse("OK")