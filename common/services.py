from django.contrib.auth.models import User
from djangotoolbox.http import JSONResponse

def is_email_available(request):
    return is_user_property_available(request, "email")

def is_username_available(request):
    return is_user_property_available(request,"username")

def is_user_property_available(request, prop_name):
    #TODO_WB:throttle this
    result = False

    if prop_name:
#        time.sleep(1)
        prop_value = request.GET.get(prop_name, None)
        result = User.objects.filter(**{prop_name: prop_value}).count() == 0

    return JSONResponse(result)
