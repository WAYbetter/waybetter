# Create your views here.
from django.http import HttpResponse
from django.utils.translation import get_language_from_request
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from djangotoolbox.http import JSONResponse
from common.decorators import catch_view_exceptions
from ordering.decorators import passenger_required_no_redirect
from ordering.forms import OrderForm
from ordering.models import Passenger
import settings
import re

POINT_ID_REGEXPT = "^(p\d+)_"

@catch_view_exceptions
@passenger_required_no_redirect
def hotspot_ordering_page(request, passenger):
    # these should match the fields of utils.Address._fields
    hidden_fields = ["city", "street_address", "house_number", "country", "geohash", "lon", "lat"]

    if request.method == 'POST':
        response = ''
        hotspot_type_raw = request.POST.get("hotspot_type", None)

        if hotspot_type_raw in ["pickup", "dropoff"]:
            hotspot_type, point_type = ("from", "to") if hotspot_type_raw == "pickup" else ("to", "from")

            fields = ["raw"] + hidden_fields
            hotspot_data = {}
            for f in fields:
                hotspot_data["%s_%s" % (hotspot_type, f)] = request.POST.get("hotspot_%s" % f, None)

            if all(hotspot_data.values()):
                p_names = []
                for f in request.POST.keys():
                    p_name = re.search(POINT_ID_REGEXPT, f)
                    if p_name and p_name.groups()[0] not in p_names:
                        p_names.append(p_name.groups()[0])

                points = []
                for p_name in p_names:
                    p_data = {}
                    for f in fields:
                        p_data["%s_%s" % (point_type, f)] = request.POST.get("%s_%s" % (p_name, f), None)

                    if all(p_data.values()):
                        points.append(p_data)

                orders = ""
                created = 0
                for p_data in points:
                    form_data = p_data.copy()
                    form_data.update(hotspot_data)
                    form = OrderForm(form_data)
                    if form.is_valid():
                        order = form.save(commit=False)
                        order.passenger = passenger
                        order.save()
                        orders += "%s<br/>" % unicode(order)
                        created += 1

                response = u"created %d orders: <br> <dir='rtl'>%s" % (created, orders)

            else:
                response = "Hotspot data corrupt"
        else:
            response = "Hotspot type invalid"

        return HttpResponse(response)

    else: # GET
        page_specific_class = "hotspot_page"
        hotspot_times = ["11:00","11:30","12:00"]

        telmap_user = settings.TELMAP_API_USER
        telmap_password = settings.TELMAP_API_PASSWORD
        telmap_languages = 'he' if str(get_language_from_request(request)) == 'he' else 'en'
        country_code = settings.DEFAULT_COUNTRY_CODE

        passenger = Passenger.from_request(request)

        return render_to_response('hotspot_ordering_page.html', locals(), context_instance=RequestContext(request))


