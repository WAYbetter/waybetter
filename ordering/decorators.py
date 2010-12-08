from django.contrib.auth.decorators import login_required
from ordering.models import Passenger, WorkStation, Station
from django.http import HttpResponseForbidden
from common.util import log_event, EventType
from django.shortcuts import render_to_response

NOT_A_USER = "NOT_A_USER"
NOT_A_PASSENGER = "NOT_A_PASSENGER"

def internal_task_on_queue(queue_name):
    """
    Ensures request has the matching HTTP_X_APPENGINE_QUEUENAME header
    """
    def actual_decorator(function):

        def wrapper(request):
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
        if (not request.user or not request.user.is_authenticated()):
            log_event(EventType.UNREGISTERED_ORDER)
            return HttpResponseForbidden(NOT_A_USER)

        try:
            passenger = Passenger.objects.filter(user = request.user).get()
            kwargs["passenger"] = passenger
        except Passenger.DoesNotExist:
            log_event(EventType.UNREGISTERED_ORDER)
            return HttpResponseForbidden(NOT_A_PASSENGER)
        return function(request, **kwargs)

    return wrapper


def passenger_required(function=None):
    """
    Decorator for views that checks that the user is logged in and is a passenger
    """
    @login_required
    def wrapper(request, **kwargs):
        try:
            passenger = Passenger.objects.filter(user = request.user).get()
            kwargs["passenger"] = passenger
        except Passenger.DoesNotExist:
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
    @login_required
    def wrapper(request, **kwargs):
        try:
            station = Station.objects.filter(user = request.user).get()
            kwargs["station"] = station
        except Station.DoesNotExist:
            return HttpResponseForbidden("You are not a station")
        return function(request, **kwargs)

    return wrapper
