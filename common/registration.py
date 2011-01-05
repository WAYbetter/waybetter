from django.shortcuts import render_to_response
from common.models import Country
from django.conf import settings
from django.template.context import RequestContext
from ordering.forms import FeedbackForm
from ordering.models import Passenger

FACEBOOK_APP_ID = getattr(settings, 'FACEBOOK_APP_ID', '')
def get_login_form(request):
    return render_to_response('login_form.html', {'FACEBOOK_APP_ID': FACEBOOK_APP_ID})

def feedback(request):
    passenger = Passenger.from_request(request)
    if request.POST:
        form = FeedbackForm(data=request.POST, passenger=passenger)
        if form.is_valid():
            feedback = form.save()
            feedback.passenger = passenger
            feedback.save()
    else:
        form = FeedbackForm()
        
    return render_to_response('feedback_form.html', locals(), RequestContext(request))


def get_error_form(request):
    return render_to_response('error_form.html')

def get_registration_form(request):
    return render_to_response('registration_form.html', {'FACEBOOK_APP_ID': FACEBOOK_APP_ID})

def get_phone_code_form(request):
    return render_to_response('code_form.html')

def get_sending_form(request):
    return render_to_response('sending_form.html')

def get_phone_form(request):
    countries = Country.objects.all()
    country_id = Country.get_id_by_code(settings.DEFAULT_COUNTRY_CODE)
    return render_to_response('phone_verification_form.html', locals())
