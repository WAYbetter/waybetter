import logging
from django.conf import settings
from django.http import HttpResponse
from common.models import CityArea, Message
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.utils import simplejson
from django.views.decorators.cache import never_cache
from djangotoolbox.http import JSONResponse
from ordering.models import Passenger

def is_email_available(request):
    return is_user_property_available(request, "email")


@never_cache
def is_user_authenticated(request):
    if request.user.is_authenticated():
        logging.info("User is authenticated: %s" % request.user.username)
        response_data = [True, request.user.username]
        passenger = Passenger.from_request(request)
        if passenger and request.is_secure(): # send token only over secure connection
            response_data.append(passenger.login_token)

        return JSONResponse(response_data)
    else:
        logging.info("User is not authenticated")
        return JSONResponse([False])

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

def get_messages(request):
    messages = Message.objects.all()
    res = {}
    for m in messages:
        res[m.key] = m.content

    return JSONResponse(res)

@staff_member_required
def get_polygons(request):
    city_areas_ids = simplejson.loads(request.POST['data'])

    result = []
    for city_area in CityArea.objects.filter(id__in=city_areas_ids):
        result.append({
            city_area.id: city_area.points
        })

    return JSONResponse(result)

@staff_member_required
def update_city_area_order(request):
    new_order = simplejson.loads(request.POST['data'])
    for city_area_id in new_order.keys():
        ca = CityArea.by_id(city_area_id)
        ca.set_order(new_order[city_area_id])
        ca.save()
        
    return JSONResponse("")

@staff_member_required
def init_model_order(request, model_name):
    from django.db.models.loading import get_model
    fixed_model_name = "".join(map(lambda s: s.title(), model_name.split("_")))
    for app in settings.INSTALLED_APPS:
        model = get_model(app, fixed_model_name)
        if model:
            model.init_order()
            return HttpResponse("OK")

    return HttpResponse("No model found for: %s" % model_name)

