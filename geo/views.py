from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render_to_response
from geo.models import Place

@staff_member_required
def add_place(request):
    lib_ng = True
    lib_map = True
    lib_geo = True

    if request.method == "GET":
        return render_to_response("add_place.html")
    else:
        place = Place()
        place.save()