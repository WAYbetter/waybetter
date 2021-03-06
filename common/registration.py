import logging
from django.shortcuts import render_to_response
from django.conf import settings
from django.template.context import RequestContext
from django.http import HttpResponseForbidden
from ordering.forms import FeedbackForm
from ordering.models import Passenger, Feedback

FACEBOOK_APP_ID = getattr(settings, 'FACEBOOK_APP_ID', '')
def get_login_form(request):
    return render_to_response('login_form.html', {'FACEBOOK_APP_ID': FACEBOOK_APP_ID, 'next': '/social/login/done/'})

def feedback(request):
    passenger = Passenger.from_request(request)
    if request.POST:
        form = FeedbackForm(data=request.POST, passenger=passenger)
        if form.is_valid():
            for name in Feedback.field_names():
                if form.cleaned_data[name]:
                    logging.info("saving feedback")
                    feedback = form.save()
                    feedback.passenger = passenger
                    feedback.save()
                    break

    else:
        form = FeedbackForm()
        
    return render_to_response('feedback_form.html', locals(), RequestContext(request))


def get_error_form(request):
    return render_to_response('error_form.html')

def get_registration_form(request):
    return render_to_response('registration_form.html', {'FACEBOOK_APP_ID': FACEBOOK_APP_ID})

def get_credentials_form(request):
    passenger = Passenger.from_request(request)
    if passenger and passenger.user:
        current_email = passenger.user.email
        context = locals()
        context.update({'FACEBOOK_APP_ID' : FACEBOOK_APP_ID})
        return render_to_response('credentials_form.html', context)
    else:
        return HttpResponseForbidden()

def get_phone_code_form(request):
    return render_to_response('code_form.html')

def get_sending_form(request):
    return render_to_response('sending_form.html')

def get_phone_form(request):
    country_code = settings.DEFAULT_COUNTRY_CODE
    return render_to_response('phone_verification_form.html', locals())

def get_cant_login_form(request):
    country_code = settings.DEFAULT_COUNTRY_CODE
    return render_to_response('cant_login_form.html', locals())