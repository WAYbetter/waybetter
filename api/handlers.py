from api.decorators import require_api_user
from common.geocode import geohash_encode, structured_geocode
from common.models import Country, City
from common.route import calculate_time_and_distance
from common.util import EventType, log_event
from django.shortcuts import get_object_or_404
from ordering.forms import OrderForm, ErrorCodes
from ordering.models import Passenger
from ordering.order_manager import book_order_async
from django.utils import translation
from piston.handler import AnonymousBaseHandler
from piston.utils import rc, require_mime

def is_valid_address(order_data, address_type):
        order_country = order_data.get(address_type + '_country')
        order_city = order_data.get(address_type + '_city')
        order_street_address = order_data.get(address_type + '_street_address')
        order_house_number = order_data.get(address_type + '_house_number')

        # empty address are "valid"
        if not len(order_country + order_city + order_street_address + order_house_number):
            return True

        addresses = structured_geocode(order_country, order_city, order_street_address, order_house_number)

        for address in addresses:
            if address["house_number"]  == order_house_number \
                and address["city"]     == order_city \
                and address["country"]  == order_country \
                and address["street_address"]   == order_street_address:

                order_data[address_type + "_raw"] = address["name"]
                order_data[address_type + "_lon"] = address["lon"]
                order_data[address_type + "_lat"] = address["lat"]
                order_data[address_type + "_geohash"] = geohash_encode(address["lon"], address["lat"])
                return True

        return False

class RideEstimateHanlder(AnonymousBaseHandler):
    allowed_methods = ('POST', )

    @require_mime('xml', 'json')
    @require_api_user()
    def create(self, request, *args, **kwargs):
        request_data = request.data.get("request")
        for address_type in ('from', 'to'):
            for att, val in request_data[address_type].items():
                request_data[address_type + "_" + att] = val or ""

            if not is_valid_address(request_data, address_type):
                res = rc.BAD_REQUEST
                res.write(" %s\n" % ErrorCodes.INVALID_ADDRESS)
                return res

        try:
            from_lon = request_data["from_lon"]
            from_lat = request_data["from_lat"]
            to_lon = request_data["to_lon"]
            to_lat = request_data["to_lat"]
        except KeyError:
            return rc.BAD_REQUEST

        result = calculate_time_and_distance(from_lon, from_lat, to_lon, to_lat)

        return {
            "ride_estimate_result": result
        }

class OrderRideHandler(AnonymousBaseHandler):
    allowed_methods = ('POST', )

    @require_mime('xml', 'json')
    @require_api_user()
    def create(self, request, *args, **kwargs):
        api_user = kwargs["api_user"]
        request_data = request.data.get("request")
        if not request_data:
            return rc.BAD_REQUEST

        language_code = request_data.get("language_code")
        translation.activate(language_code)

        passenger = None
        phone_number = request_data.get("phone_number")
        login_token = request_data.get("login_token")

        try:
            if login_token: #TODO_WB: merge needed to make this work
                passenger = Passenger.objects.get(login_token=login_token)
            elif phone_number and not api_user.phone_validation_required:
                passenger = Passenger.objects.get(phone=phone_number) 
        except Passenger.DoesNotExist:
            pass

        if not passenger:
            return rc.NOT_FOUND #TODO_WB: is this the right response

        order_data = {}
        for address_type in ('from', 'to'):
            for att, val in request_data[address_type].items():
                order_data[address_type + "_" + att] = val or ""

            if not is_valid_address(order_data, address_type):
                res = rc.BAD_REQUEST
                res.write(" %s\n" % ErrorCodes.INVALID_ADDRESS)
                return res

            order_data[address_type + "_country"] = Country.get_id_by_code(order_data[address_type + "_country"])
            order_data[address_type + "_city"] = City.get_id_by_name_and_country(order_data[address_type + "_city"], order_data[address_type + "_country"], add_if_not_found=True)

        order_form = OrderForm(data=order_data, passenger=passenger)
        if order_form.is_valid():

            order = order_form.save()
            order.api_user = api_user
            order.passenger = passenger
            order.language_code = language_code
            order.save()
            book_order_async(order)
            log_event(EventType.ORDER_BOOKED, order=order)
            return rc.CREATED
        else:
            response = rc.BAD_REQUEST
            response.write(" %s\n" % order_form.errors.as_text())
            return response


