from django.shortcuts import render_to_response
from stations.decorators import station_required
from django.conf import settings

#@station_required(login_url=settings.STATION_LOGIN_URL)
from django.contrib.auth.decorators import user_passes_test
import logging

@user_passes_test(lambda u: u.is_authenticated(), login_url=settings.STATION_LOGIN_URL)
@station_required
def station_home(request, station):
    return render_to_response("station_home.html", locals())

def stations_home(request):
    return render_to_response("station_home.html")

def login(request):
    logging.info('login')
    return render_to_response("registration/login.html")
    