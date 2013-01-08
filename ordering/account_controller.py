import hashlib
import logging
from billing.billing_manager import get_token_url
from django.contrib.auth.models import User
from django.utils.translation import ugettext as _
from common.models import Country
from common.util import generate_random_token
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.http import  HttpResponseBadRequest, HttpResponseNotAllowed, HttpResponse
from django.shortcuts import render_to_response
from django.template import RequestContext
from djangotoolbox.http import JSONResponse
from ordering.models import Passenger, CURRENT_PASSENGER_KEY
from ordering.util import get_name_parts, create_user, create_passenger

def account_view(request):
    if request.user.is_authenticated():
            user = request.user
            passenger = user.passenger
            name = user.get_full_name()
            email = user.email
            phone = passenger.phone
            billing_info = passenger.billing_info.card_repr[-4:] if hasattr(passenger, "billing_info") else None

            return render_to_response("mobile/account_registration.html", locals(), RequestContext(request))
    else:
        return registration_view(request)

def registration_view(request):
    if request.user.is_authenticated():
        return account_view(request)

    if request.method == 'GET':
        # TODO: BI log
        return render_to_response("mobile/account_registration.html", locals(), RequestContext(request))

    elif request.method == 'POST':
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        country = Country.objects.get(code=settings.DEFAULT_COUNTRY_CODE)

        try:  # TODO: email already exists
            user = User.objects.get(username=email)
            if user:
                logging.info("email %s already registered" % email)# notify?
                return HttpResponseBadRequest(_("Email already registered"))
        except User.DoesNotExist:
            pass

        try:  # TODO: phone already exists
            passenger = Passenger.objects.get(phone=phone, country=country)
            if passenger:
                logging.info("phone %s already registered" % phone) # notify?
                return HttpResponseBadRequest(_("Phone already registered"))
        except Passenger.DoesNotExist:
            pass


        user = register_new_user(request)
        if user:
            return get_billing_url(request)
        else:
            return HttpResponseBadRequest(_('Registration failed'))

    else:
        return HttpResponseNotAllowed(request.method)

def register_new_user(request):
    logging.info("registration %s" % request.POST)

    name = request.POST.get("name")
    email = request.POST.get("email")
    password = request.POST.get("password")
    phone = request.POST.get("phone")

    first_name, last_name = get_name_parts(name)
    user = create_user(email, password, email, first_name, last_name)
    user = authenticate(username=user.username, password=password)
    login(request, user)

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