from django.contrib.auth.decorators import login_required
from ordering.models import Passenger, Station, WorkStation
from django.http import HttpResponseForbidden

def passenger_required(function):
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

def station_required(function):
    """
    Decorator for views that checks that the user is logged in and is a station
    """
    @login_required
    def wrapper(request, **kwargs):
        if Station.objects.filter(user = request.user).count() < 1:
            return HttpResponseForbidden("You are not a station")
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
            return HttpResponseForbidden("You are not a workstation, please <a href='/workstation/logout/'>logout</a> and try again")

        return function(request, **kwargs)

    return wrapper