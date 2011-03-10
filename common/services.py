import time

from django.http import HttpResponse
from django.db.models.loading import get_model

def is_username_available(request):
    return is_model_property_available("auth", "user", "username", request)

def is_email_available(request):
    return is_model_property_available("auth", "user", "email", request)

def is_model_property_available(app_name, model_name, property_name, request):
    #TODO_WB:throttle this
    result = False
    property = request.GET.get(property_name)
    if (property):
        time.sleep(1)
        model = get_model(app_name, model_name)
        result = model.objects.filter(**{property_name: property}).count() == 0

    if result:
        return HttpResponse("true")
    else:
        return HttpResponse("false")