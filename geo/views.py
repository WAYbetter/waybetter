from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseBadRequest
from django.shortcuts import render_to_response
from django.views.decorators.csrf import csrf_exempt
from djangotoolbox.http import JSONResponse
import logging
import simplejson

from common.models import City
from geo.models import Place

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

        if action in ["create", "update"]:
            if place_data.get("city_name"):
                place_data["city"] = City.objects.get(name=place_data["city_name"].strip())
                del(place_data["city_name"])

            place_data["aliases"] = place_data["aliases"].split(",")

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