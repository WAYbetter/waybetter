from common.models import  Country
from common.geocode import geohash_encode
from common.tz_support import set_default_tz_time
from django.http import HttpResponse, HttpResponseForbidden
from django.utils.translation import get_language_from_request
from django.shortcuts import render_to_response, get_object_or_404
from django.template.context import RequestContext
from djangotoolbox.http import JSONResponse
from ordering.decorators import passenger_required
from ordering.forms import OrderForm
from sharing.forms import ProducerPassengerForm
from sharing.passenger_controller import HIDDEN_FIELDS
from sharing.models import HotSpot, Producer, ProducerPassenger
from sharing.algo_api import submit_orders_for_ride_calculation
from datetime import  datetime, date
import re
import time
import settings

@passenger_required
def producer_ordering_page(request, passenger):
    if not hasattr(passenger, "producer"):
        return HttpResponseForbidden("You are not a producer")
    
    if request.method == 'POST':
        response = ''
        hotspot_type_raw = request.POST.get("hotspot_type", None)

        if hotspot_type_raw in ["pickup", "dropoff"]:
            response = "No orders created"

            hotspot_type = "from" if hotspot_type_raw == "pickup" else "to"
            orders = create_orders(request.POST, hotspot_type, passenger.producer)
            shared_orders = orders.get('shared_orders')
            not_shared_orders = orders.get('not_shared_orders')

            wb_data = ""
            if shared_orders:
                res = submit_orders_for_ride_calculation(orders['shared_orders'])
                response = u"%d orders submitted for sharing" % len(shared_orders)
                wb_data = u"sharing keys: %s" % res.content.strip()
            if not_shared_orders:
                algo_keys = []
                for order in not_shared_orders:
                    res = submit_orders_for_ride_calculation([order])
                    algo_keys.append(res.content.strip())
                response += u"</br>%d orders not shared" % len(not_shared_orders)
                wb_data += u"<br/>non sharing keys: %s" % " ".join(algo_keys)

            if wb_data:
                response = "%s %s %s" % (response, "</br></br></br>For internal use by WAYbetter:</br>", wb_data)
        else:
            response = "Hotspot type invalid"

        return HttpResponse(response)

    else: # GET
        is_popup = True
        page_specific_class = "producer_page"

        hidden_fields = HIDDEN_FIELDS
        producer = passenger.producer
        hotspots = [{'name': hotspot.name, 'id': hotspot.id, 'lon': hotspot.lon, 'lat': hotspot.lat}
        for hotspot in HotSpot.objects.all()]

        telmap_user = settings.TELMAP_API_USER
        telmap_password = settings.TELMAP_API_PASSWORD
        telmap_languages = 'he' if str(get_language_from_request(request)) == 'he' else 'en'
        country_code = settings.DEFAULT_COUNTRY_CODE

        return render_to_response('producer_ordering_page.html', locals(), context_instance=RequestContext(request))


def new_producer_passenger(request):
    response = 'OK'
    if request.method == 'POST':
        data = request.POST.copy()
        data.update({
            'address': request.POST.get('address_raw'),
            'city': request.POST.get('address_city'),
            'street_address': request.POST.get('address_street_address'),
            'house_number': request.POST.get('address_house_number'),
            'lat': request.POST.get('address_lat'),
            'lon': request.POST.get('address_lon')})

        form = ProducerPassengerForm(data)
        if form.is_valid():
            p = form.save(commit=False)
            producer = get_object_or_404(Producer, id=request.POST['producer_id'])
            p.producer = producer
            p.geohash = geohash_encode(p.lon, p.lat)
            p.country = Country.objects.get(code=settings.DEFAULT_COUNTRY_CODE)
            p.save()
        else:
            response = {"error": "error"}
        return JSONResponse(response)

    else:
        return HttpResponse(response)


def get_producer_passengers(request):
    producer = get_object_or_404(Producer, id=request.GET['producer_id'])
    passengers = [{'name': p.name, 'id': p.id, 'address': p.address, 'is_sharing': p.is_sharing, 'phone': p.phone, 'lon': p.lon, 'lat': p.lat}
        for p in producer.passengers.all().order_by("name")]
    return JSONResponse({'passengers': passengers})


# utility methods
PASSENGER_ID_REGEXP = re.compile("^p\d+_select")

def create_orders(data, hotspot_type, producer):
    hotspot = HotSpot.by_id(data.get("hotspot_id"))
    hotspot_data = hotspot.serialize_for_order(hotspot_type)

    hotspot_time = datetime.strptime(data.get("hotspot_time"), "%H:%M").time()
    hotspot_date = date(*time.strptime(data.get("hotspot_date"), '%d/%m/%Y')[:3])
    hotspot_datetime = set_default_tz_time(datetime.combine(hotspot_date, hotspot_time))

    passenger_ids = [data.get(f) for f in filter(lambda f: re.search(PASSENGER_ID_REGEXP, f), data.keys())]
    passengers = filter(lambda p: p and p.producer == producer, [ProducerPassenger.by_id(x) for x in passenger_ids])

    shared_orders = []
    not_shared_orders = []

    for p in passengers:
        form_data = p.serialize_for_order("from" if hotspot_type == "to" else "to")
        form_data.update(hotspot_data)
        form = OrderForm(form_data)
        if form.is_valid():
            order = form.save(commit=False)
            order.passenger = p.passenger
            if hotspot_type == "from":
                order.depart_time = hotspot_datetime
            else:
                order.arrive_time = hotspot_datetime

            order.confining_station = producer.default_sharing_station
            order.save()

            if p.is_sharing:
                shared_orders.append(order)
            else:
                not_shared_orders.append(order)

    return {'shared_orders': shared_orders, 'not_shared_orders': not_shared_orders}