from django.contrib.auth.models import User
from djangotoolbox.http import JSONResponse
from ordering.models import Passenger

def is_email_available(request):
    return is_user_property_available(request, "email")


def is_email_available_for_user(request):
    passenger = Passenger.from_request(request)
    if passenger and passenger.user:
        if request.GET.get("email", None) == passenger.user.email:
            return JSONResponse(True)

    return is_email_available(request)


def is_username_available(request):
    return is_user_property_available(request, "username")


def is_user_property_available(request, prop_name):
    #TODO_WB:throttle this
    result = False

    prop_value = request.GET.get(prop_name, None)
    if prop_value:
    #        time.sleep(1)
        result = User.objects.filter(**{prop_name: prop_value}).count() == 0

    return JSONResponse(result)
