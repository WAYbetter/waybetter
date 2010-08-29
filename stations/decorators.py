from django.http import HttpResponseForbidden
from ordering.models import Station
from django.contrib.auth.decorators import login_required


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
