import time
from django.contrib.auth.models import User
from django.http import HttpResponse

def is_email_available(request):
    return is_user_property_available("email", request.GET.get("email", None))

def is_username_available(request):
    return is_user_property_available("username", request.GET.get("username", None))

def is_user_property_available(prop_name, prop_value):
    #TODO_WB:throttle this
    result = False

    if prop_name:
        time.sleep(1)
        result = User.objects.filter(**{prop_name: prop_value}).count() == 0

    if result:
        return HttpResponse("true")
    else:
        return HttpResponse("false")
