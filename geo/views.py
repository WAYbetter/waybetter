# -*- coding: utf-8 -*-

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseBadRequest, HttpResponse
from django.shortcuts import render_to_response
from django.views.decorators.csrf import csrf_exempt
from djangotoolbox.http import JSONResponse
import logging
import simplejson

from common.util import dict_to_str_keys
from common.models import City
from geo.models import Place

def playground(request):
    lib_ng = True
    lib_map = True
    lib_geo = True

    places = simplejson.dumps([place.serialize() for place in Place.objects.all()])

    return render_to_response("playground.html", locals())


def get_places(request):
    def place_to_suggestion(place, name=None):
        return {
            'id': place.id,
            'name': name or place.name_for_user,
            'description': place.description_for_user,
            'city_name': place.dn_city_name,
            'street': place.street,
            'house_number': place.house_number,
            'lon': place.lon,
            'lat': place.lat,
            'country_code': settings.DEFAULT_COUNTRY_CODE
        }

    places_data = []
    for place in Place.objects.all():
        places_data.append(place_to_suggestion(place))

        for alias in place.aliases:
            places_data.append(place_to_suggestion(place, name=alias))

    return JSONResponse({
        "places": places_data,
        "blacklist": ['תל אביב, ישראל']
    })

@csrf_exempt  # TODO_WB: teach angular to pass csrf_token in headers
@staff_member_required
def crud_place(request):
    lib_ng = True
    lib_map = True
    lib_geo = True

    if request.method == "GET":
        places = simplejson.dumps([place.serialize() for place in Place.objects.all()])
        return render_to_response("crud_place.html", locals())

    elif request.method == "POST":  # CRUD actions
        payload = simplejson.loads(request.raw_post_data)
        action = payload["action"]
        place_data = payload["data"]
        place_data = dict_to_str_keys(place_data)

        if action in ["create", "update"]:
            if place_data.get("city_name"):
                place_data["city"] = City.objects.get(name=place_data["city_name"].strip())
                del(place_data["city_name"])

            place_data["aliases"] = place_data["aliases"]

            if action == "create":
                place = Place(**place_data)
                place.save()
                logging.info("created new place: %s" % place.name)

            else:  # update
                place = Place.by_id(place_data["id"])
                del(place_data["id"])
                place.update(**place_data)
                logging.info("updated place %s" % place.name)

            return JSONResponse({'place': place.serialize()})

        elif action == "remove":
            place = Place.by_id(place_data["id"])
            deleted = False
            if place:
                place.delete()
                deleted = True
                logging.info("deleted place %s" % place.name)

            return JSONResponse({'success': deleted})

    return HttpResponseBadRequest()