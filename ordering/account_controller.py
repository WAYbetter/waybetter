import hashlib
import logging
from billing.billing_manager import get_token_url
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _
from common.models import Country
from common.util import generate_random_token, custom_render_to_response
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotAllowed, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext
from djangotoolbox.http import JSONResponse
from ordering.models import Passenger, CURRENT_PASSENGER_KEY
from ordering.util import get_name_parts, create_user, create_passenger

def registration(request):
    # TODO: BI log

    if request.user.is_authenticated():
        return HttpResponseRedirect(reverse('wb_home'))

    if request.method == 'GET':
        return render_to_response("mobile/account_registration.html", locals(), RequestContext(request))

    elif request.method == 'POST':
        name = request.POST.get("name")
        email = request.POST.get("email")
        password = request.POST.get("password")
        phone = request.POST.get("phone")
        # promo_code = request.POST.get("promo_code")

        required_fields = [name, email, password, phone]
        logging.info("registration %s" % required_fields)
        if all(required_fields):
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


            # registration starts here
            first_name, last_name = get_name_parts(name)
            user = create_user(email, password, email, first_name, last_name)
            user = authenticate(username=user.username, password=password)
            login(request, user)

            passenger = create_passenger(request.user, country, phone, save=False)
            passenger.login_token = hashlib.sha1(generate_random_token(length=40)).hexdigest()
            passenger.save()

            request.session[CURRENT_PASSENGER_KEY] = passenger

            logging.info("account registration completed")
            return JSONResponse({'redirect': get_token_url(request)})

        else:
            return HttpResponseBadRequest('Please fill out all required fields')

    else:
        return HttpResponseNotAllowed(request.method)
