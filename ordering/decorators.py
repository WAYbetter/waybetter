from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.utils.http import urlquote
from ordering.models import Passenger, WorkStation, Station, OrderAssignment, Order
from django.http import HttpResponseForbidden, HttpResponseRedirect, HttpResponse, HttpResponseBadRequest
from django.shortcuts import render_to_response
from django.conf import settings

import logging

NOT_A_USER = "NOT_A_USER"
NOT_A_PASSENGER = "NOT_A_PASSENGER"

def login_needed(login_url):
    return user_passes_test(lambda u: not u.is_anonymous(), login_url=login_url)


def require_parameters(method='GET', required_params=()):
    """
    Ensure the given parameters where passed to the request, otherwise respond with HttpResponseBadRequest
    """

    def actual_decorator(function):
        def wrapper(request):
            dic = getattr(request, method)
            if not all([p in dic for p in required_params]):
                return HttpResponseBadRequest("Missing parameters")

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
            work_station = WorkStation.objects.get(user=request.user)
            kwargs["work_station"] = work_station
        except WorkStation.DoesNotExist:
            from django.contrib.auth import REDIRECT_FIELD_NAME
            next = urlquote(request.get_full_path())
            login_url = settings.LOGIN_URL
            redirect_field_name = REDIRECT_FIELD_NAME
            return HttpResponseRedirect('%s?%s=%s' % (login_url, redirect_field_name, next))

        return function(request, **kwargs)

    return wrapper


def station_required(function=None):
    """
    Decorator for views that checks that the user is logged in and is a station
    """

    @login_needed(settings.STATION_LOGIN_URL)
    def wrapper(request, **kwargs):
        try:
            station = Station.objects.get(user=request.user)
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
            station = Station.objects.filter(user=request.user).get()
            kwargs["station"] = station
        except Station.DoesNotExist:
        #            return HttpResponseForbidden("You are not a station")
            try:
                work_station = WorkStation.objects.get(user=request.user)
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
            order_assignment = OrderAssignment.objects.get(id=order_assignment_id)
            kwargs["order_assignment"] = order_assignment
        except OrderAssignment.DoesNotExist:
            logging.error("No order assignment found for id: %d" % order_assignment_id)
            return HttpResponse("No order assignment found")

        return function(request, **kwargs)

    return wrapper


def order_required(function=None):
    def wrapper(request, **kwargs):
        order_id = int(request.POST["order_id"])
        try:
            order = Order.objects.get(id=order_id)
            kwargs["order"] = order
        except Order.DoesNotExist:
            logging.error("No order found for id: %d" % order_id)
            return HttpResponse("No order found")

        return function(request, **kwargs)

    return wrapper
