from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.utils.http import urlquote
from ordering.models import Passenger, WorkStation, Station, CURRENT_PASSENGER_KEY
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.conf import settings

NOT_A_USER = "NOT_A_USER"
NOT_A_PASSENGER = "NOT_A_PASSENGER"

def login_needed(login_url):
    return user_passes_test(lambda u: not u.is_anonymous(), login_url=login_url)

def internal_task_on_queue(queue_name):
    """
    Ensures request has the matching HTTP_X_APPENGINE_QUEUENAME header
    """
    def actual_decorator(function):

        def wrapper(request):
            if hasattr(request, '_dont_enforce_csrf_checks' ) and request._dont_enforce_csrf_checks:
                return function(request)
            
            if request.META.get('HTTP_X_APPENGINE_QUEUENAME', "") != queue_name:
                return HttpResponseForbidden("Invalid call to internal task")

            return function(request)

        return wrapper

    return actual_decorator

def passenger_required_no_redirect(function=None):
    """
    Decorator for views that checks that the user is logged in and is a passenger
    """
    def wrapper(request, **kwargs):
        passenger = Passenger.from_request(request)

        if not passenger:
            return HttpResponseForbidden(NOT_A_PASSENGER)

        kwargs["passenger"] = passenger
        return function(request, **kwargs)

    return wrapper


def passenger_required(function=None):
    """
    Decorator for views that checks that the user is logged in and is a passenger
    """
    @login_required
    def wrapper(request, **kwargs):
        passenger = Passenger.from_request(request)
        if passenger:
            kwargs["passenger"] = passenger
        else:
            return HttpResponseForbidden("You are not a passenger, please <a href='/passenger/logout/'>logout</a> and try again")
        return function(request, **kwargs)

    return wrapper



def work_station_required(function):
    """
    Decorator for views that checks that the user is logged in and is a station
    """
    @login_required
    def wrapper(request, **kwargs):
        try:
            work_station = WorkStation.objects.filter(user = request.user).get()
            kwargs["work_station"] = work_station
        except WorkStation.DoesNotExist:
#            return HttpResponseForbidden("You are not a workstation, please <a href='/workstation/logout/'>logout</a> and try again")
            return render_to_response("wrong_user_type_message.html", {})

        return function(request, **kwargs)

    return wrapper


def station_required(function=None):
    """
    Decorator for views that checks that the user is logged in and is a station
    """
    @login_needed(settings.STATION_LOGIN_URL)
    def wrapper(request, **kwargs):
        try:
            station = Station.objects.filter(user = request.user).get()
            kwargs["station"] = station
        except Station.DoesNotExist:
             logout(request)
             path = urlquote(request.get_full_path())
             return HttpResponseRedirect(path)

        return function(request, **kwargs)

    return wrapper

def station_or_workstation_required(function=None):
    @login_needed(settings.STATION_LOGIN_URL)
    def wrapper(request, **kwargs):
        try:
            station = Station.objects.filter(user = request.user).get()
            kwargs["station"] = station
        except Station.DoesNotExist:
#            return HttpResponseForbidden("You are not a station")
            try:
                work_station = WorkStation.objects.filter(user = request.user).get()
                kwargs["station"] = work_station.station
            except WorkStation.DoesNotExist:
                logout(request)
                path = urlquote(request.get_full_path())
                return HttpResponseRedirect(path)
#            return HttpResponseForbidden("You are not a workstation, please <a href='/workstation/logout/'>logout</a> and try again")
#                return render_to_response("wrong_user_type_message.html", {})

        return function(request, **kwargs)

    return wrapper
