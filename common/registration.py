from django.shortcuts import render_to_response
from common.models import Country
from django.conf import settings

FACEBOOK_APP_ID = getattr(settings, 'FACEBOOK_APP_ID', '')
def get_login_form(request):

    return render_to_response('login_form.html', {'FACEBOOK_APP_ID': FACEBOOK_APP_ID})

def get_registration_form(request):
    return render_to_response('registration_form.html', {'FACEBOOK_APP_ID': FACEBOOK_APP_ID})

def get_phone_code_form(request):
    return render_to_response('code_form.html')

def get_sending_form(request):
    return render_to_response('sending_form.html')

def get_phone_form(request):
    countries = Country.objects.all()
    default_country_code = settings.DEFAULT_COUNTRY_CODE
    return render_to_response('phone_verification_form.html', locals())
