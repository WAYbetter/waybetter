from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.utils.http import urlquote
from ordering.models import Passenger, WorkStation, Station, CURRENT_PASSENGER_KEY, OrderAssignment
from django.http import HttpResponseForbidden, HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response
from django.conf import settings

import logging

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
        passenger = None
        if request.user.is_authenticated():
            try:
                passenger = Passenger.objects.filter(user = request.user).get()
            except Passenger.DoesNotExist:
                pass

        if not passenger:
            passenger = request.session.get(CURRENT_PASSENGER_KEY, None)

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

def order_assignment_required(function=None):
    def wrapper(request, **kwargs):
        order_assignment_id = int(request.POST["order_assignment_id"])
        try:
            order_assignment = OrderAssignment.objects.filter(id=order_assignment_id).get()
            kwargs["order_assignment"] = order_assignment
        except OrderAssignment.DoesNotExist:
            logging.error("No order assignment found for id: %d" % order_assignment_id)
            return HttpResponse("No order assignment found")

        return function(request, **kwargs)

    return wrapper