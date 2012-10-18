# -*- coding: utf-8 -*-
from __future__ import absolute_import # we need absolute imports since ordering contains pricing.py

import logging
import traceback
import urllib
from django.core.urlresolvers import reverse
from django.utils.translation import get_language_from_request
from django.views.decorators.csrf import csrf_exempt
from billing.billing_manager import  get_token_url
from billing.enums import BillingStatus
from billing.models import BillingTransaction
from common.tz_support import to_js_date, default_tz_now, utc_now, ceil_datetime
from common.util import first, Enum, dict_to_str_keys, datetimeIterator, notify_by_email
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from django.conf import settings
from django.views.decorators.cache import never_cache
from django.http import HttpResponse, HttpResponseRedirect
from django.utils.translation import ugettext_lazy, ugettext as _
from djangotoolbox.http import JSONResponse
from oauth2.views import update_profile_fb
from ordering.decorators import  passenger_required_no_redirect
from ordering.models import SharedRide, NEW_ORDER_ID, RidePoint, StopType, Order, OrderType, ACCEPTED, APPROVED, PENDING, Passenger, CHARGED, RideEvent, CANCELLED
from pricing.models import TARIFFS, RuleSet
from sharing.algo_api import AlgoField
import simplejson
import datetime
import dateutil.parser

import sharing.algo_api as algo_api

WAYBETTER_STATION_NAME = "WAYbetter"

MAX_SEATS = 3
BOOKING_INTERVAL = 10 # minutes
ASAP_BOOKING_TIME = 5 # minutes
MAX_RIDE_DURATION = 15 #minutes

OFFERS_TIMEDELTA = datetime.timedelta(minutes=60)

ORDER_SUCCESS_STATUS = [APPROVED, ACCEPTED, CHARGED]

PREVIOUS_RIDES_TO_DISPLAY = 10
HISTORY_SUGGESTIONS_TO_SEARCH = 30

GENERIC_ERROR = _("Your request could not be completed.")

def staff_m2m(request):
    return render_to_response("staff_m2m.html", RequestContext(request))


@passenger_required_no_redirect
def get_ongoing_ride_details(request, passenger):
    order_id = request.GET.get("order_id")
    order = Order.by_id(order_id)

    response = {}

    if order and order.ride:
        ride = order.ride
        station = ride.station
        station_data = {
            'name': station.name if station else WAYBETTER_STATION_NAME,
            'phone': station.phone if station else settings.CONTACT_PHONE
        }

        pickup_position = {"lat": order.from_lat, "lng": order.from_lon}
        dropoff_position = {"lat": order.to_lat, "lng": order.to_lon}
        pickup_stops = [{"lat": p.lat, "lng": p.lon} for p in ride.pickup_points]  # sorted by stop_time
        sorted_orders = sorted(ride.orders.all(), key=lambda o: o.depart_time)

        # stops include other passengers stops only
        stops = filter(lambda stop: (stop["lat"], stop["lng"])
                    not in [(pickup_position["lat"], pickup_position["lng"]), (dropoff_position["lat"], dropoff_position["lng"])], pickup_stops)

        # passenger appears as many times as seats she ordered
        passengers = [{'name': o.passenger.name, 'picture_url': o.passenger.picture_url, 'is_you': o==order}
                        for o in sorted_orders for seat in range(o.num_seats)]

        response = {
            "station"           : station_data,
            "passengers"        : passengers,
            "pickup_position"   : pickup_position,
            "dropoff_position"  : dropoff_position,
            "stops"             : stops,
            "empty_seats"       : MAX_SEATS - sum([o.num_seats for o in sorted_orders]),
            "debug"             : settings.DEV,
        }

    return JSONResponse(response)


def get_ongoing_order(passenger):
    """
    @param passenger:
    @return: ongoing order or None
    """
    ongoing_order = None

    # orders that can still be ongoing
    recently = default_tz_now() - datetime.timedelta(minutes=MAX_RIDE_DURATION)
    possibly_ongoing_orders = passenger.orders.filter(depart_time__lte=default_tz_now(), depart_time__gt=recently).order_by("-depart_time")

    for order in possibly_ongoing_orders:
        if order.status in ORDER_SUCCESS_STATUS:
            ongoing_order = order
        break

    return ongoing_order

@never_cache
def sync_app_state(request):
    earliest_pickup_time = ceil_datetime(default_tz_now() + datetime.timedelta(minutes=10), minutes=BOOKING_INTERVAL)
    latest_pickup_time = earliest_pickup_time + datetime.timedelta(hours=24)
    dt_options = list(datetimeIterator(earliest_pickup_time, latest_pickup_time, delta=datetime.timedelta(minutes=BOOKING_INTERVAL)))

    response = {"pickup_datetime_options": [to_js_date(opt) for opt in dt_options],
                "pickup_datetime_default_idx": min(3, len(dt_options))}

    passenger = Passenger.from_request(request)
    response["show_url"] = "" # change to cause child browser to open with passed url

    if passenger:
        response["authenticated"] = True
        ongoing_order = get_ongoing_order(passenger)
        if ongoing_order:
            response["ongoing_order_id"] = ongoing_order.id

        future_orders = get_future_orders_for(passenger)
        response["future_orders_count"] = len(future_orders)

    logging.info("get_initial_status: %s" % response)
    return JSONResponse(response)

@passenger_required_no_redirect
def get_order_billing_status(request, passenger):
    approved = "approved"
    pending = "pending"

    order_id = request.GET.get("order_id")
    order = Order.by_id(order_id)

    if not (order and order.passenger == passenger):
        return JSONResponse({"error": _("You are not authorized to view the status of this order")})

    response = {}
    try:
        billing_trx = sorted(order.billing_transactions.all(), lambda trx: trx.create_date)[0]

        if billing_trx.status == BillingStatus.APPROVED:
            response['status'] = approved
        elif billing_trx.status == BillingStatus.FAILED:
            response['error'] = billing_trx.comments
        else:
            response['status'] = pending

    except IndexError:  # no billing transactions
        response['error'] = _("Order was not processed for billing")

    logging.info("response = %s" % response)
    return JSONResponse(response)


@passenger_required_no_redirect
def get_picture(request, passenger):
    response = {}
    if passenger.picture_url:
        response['picture_url'] = passenger.picture_url
    return JSONResponse(response)


@passenger_required_no_redirect
def update_picture(request, passenger):
    """
    Redirects the passenger to fb
    """
    callback_url = "http://%s%s" % (settings.DEFAULT_DOMAIN, reverse(update_profile_fb, args=[passenger.id]))
    fb_url = "%s?client_id=%s&redirect_uri=%s&scope=email" % (settings.FACEBOOK_CONNECT_URI, settings.FACEBOOK_APP_ID, callback_url)
    return JSONResponse({'redirect': fb_url})


def fb_share(request):
    args = {
        'app_id': settings.FACEBOOK_APP_ID,
        'link': settings.DEFAULT_DOMAIN,
        'picture': 'http://www.waybetter.com/static/images/wb_site/wb_beta_logo.png',
        'name': 'WAYbetter',
        'description': _('WAYbetter is the easiest way to get from A to B'),
        'redirect_uri': "http://%s" % settings.DEFAULT_DOMAIN,
        'display': 'touch' if request.mobile else 'page'
    }
    url = "http://%s.facebook.com/dialog/feed?%s" % ("m" if request.mobile else "www", urllib.urlencode(args))

    return HttpResponseRedirect(url)


@never_cache
@passenger_required_no_redirect
def get_history_suggestions(request, passenger):
    orders = passenger.orders.order_by('-depart_time')[:HISTORY_SUGGESTIONS_TO_SEARCH]
    orders = filter(lambda o: o.type != OrderType.PICKMEAPP, orders)
    data = set([Address.from_order(o, "from") for o in orders] + [Address.from_order(o, "to") for o in orders])
    data = [a.__dict__ for a in data]

    return JSONResponse(data)


@never_cache
@passenger_required_no_redirect
def get_previous_rides(request, passenger):
    data = []

    orders = passenger.orders.filter(depart_time__lt=utc_now(), status__in=ORDER_SUCCESS_STATUS).order_by('-depart_time')
    orders = orders.filter(type__in=[OrderType.PRIVATE, OrderType.SHARED])[:PREVIOUS_RIDES_TO_DISPLAY]
    seen_rides = []

    for order in orders:
        ride = order.ride
        if not ride:
            logging.error("order [%s] not valid for previous rides (order.ride is None" % order.id)
            continue
        if ride in seen_rides:
            continue  # skip duplicates (in case ride has multiple orders by same passenger)

        seen_rides.append(ride)

        ride_orders = ride.orders.all()
        ride_mates_orders = filter(lambda o: o != order, ride_orders)
        ride_mates = [{'name': order.passenger.name, 'picture_url': order.passenger.picture_url}
                                    for order in ride_mates_orders for seat in range(order.num_seats)]

        dispatching_event = first(lambda e: e.taxi_id, ride.events.all())

        ride_data = {
            "order_id": order.id,
            "pickup_time": to_js_date(order.pickup_point.stop_time),
            "passengers": ride_mates,
            "seats_left": MAX_SEATS - sum([order.num_seats for order in ride_orders]),
            "your_seats": order.num_seats,
            "taxi_number": dispatching_event.taxi_id if dispatching_event else None,
            "station_name": ride.station.name if ride.station else WAYBETTER_STATION_NAME,
            "price": order.price,
            "billing_status": ugettext_lazy(order.get_status_display().title()),
            "is_private": order.type == OrderType.PRIVATE
            }

        data.append(ride_data)

    return JSONResponse(data)


@never_cache
@passenger_required_no_redirect
def get_next_rides(request, passenger):
    data = []
    future_orders = get_future_orders_for(passenger)
    seen_rides = []

    for order in future_orders:
        ride = order.ride
        if not ride:
            logging.error("order [%s] not valid for previous rides (order.ride is None" % order.id)
            continue
        if ride in seen_rides:
            continue  # skip duplicates (in case ride has multiple orders by same passenger)
        seen_rides.append(ride)

        ride_orders = ride.orders.all()
        ride_mates_orders = filter(lambda o: o != order, ride_orders)
        ride_mates = [{'name': o.passenger.name, 'picture_url': o.passenger.picture_url}
                        for o in ride_mates_orders for seat in range(o.num_seats)]

        ride_data = {
            "order_id": order.id,
            "pickup_time": to_js_date(order.pickup_point.stop_time),
            "passengers": ride_mates,
            "seats_left": MAX_SEATS - sum([order.num_seats for order in ride_orders]),
            "your_seats": order.num_seats,
            "price": order.price,
            "is_private": order.type == OrderType.PRIVATE,
            "billing_status": _("or less"),
        }

        data.append(ride_data)

    return JSONResponse(data)

def get_future_orders_for(passenger):
    future_order_qs = passenger.orders.filter(depart_time__gte=utc_now()).order_by('-depart_time')
    future_order_qs.filter(status__in=ORDER_SUCCESS_STATUS, type__in=[OrderType.PRIVATE, OrderType.SHARED])
    return list(future_order_qs)


def get_candidate_rides(order_settings):
    """
    Get rides that might be a match for the given order_settings
    @param order_settings: C{OrderSettings}
    @return:
    """
    requested_pickup_dt = order_settings.pickup_dt
    earliest = max(default_tz_now(), requested_pickup_dt - OFFERS_TIMEDELTA)
    latest = requested_pickup_dt + OFFERS_TIMEDELTA

    candidate_pickups_qs = RidePoint.objects.filter(stop_time__gt=earliest, stop_time__lte=latest)
    candidate_pickups = filter(lambda p: p.type == StopType.PICKUP, candidate_pickups_qs)

    # remove duplicates: different pickups can belong to the same ride
    candidates = set([p.ride for p in candidate_pickups])

    # don't mix dev with production rides
    candidates = filter(lambda ride: ride.debug == settings.DEV, candidates)

    # remove private rides
    candidates = filter(lambda ride: ride.can_be_joined, candidates)

    # remove fully booked rides
    candidates = filter(lambda ride: sum([order.num_seats for order in ride.orders.all()]) + order_settings.num_seats <= MAX_SEATS, candidates)

    return candidates


def get_matching_rides(candidate_rides, order_settings):
    """
    Get matching rides for the given order_settings out of the candidate_rides

    @param candidate_rides:
    @param order_settings:
    @return: A list of JSON objects representing modified SharedRides
    """

    matches = algo_api.find_matches(candidate_rides, order_settings)
    return matches


def get_ride_cost_data_from(ride_data):
    return {TARIFFS.TARIFF1: (ride_data[AlgoField.COST_LIST_TARIFF1]),
             TARIFFS.TARIFF2: (ride_data[AlgoField.COST_LIST_TARIFF2])}


def get_order_price_data_from(ride_data, order_id=NEW_ORDER_ID, sharing=True):
    order_info = ride_data[AlgoField.ORDER_INFOS][str(order_id)]
    if sharing:
        return {
            TARIFFS.TARIFF1: order_info[AlgoField.PRICE_SHARING_TARIFF1],
            TARIFFS.TARIFF2: order_info[AlgoField.PRICE_SHARING_TARIFF2]
        }
    else:
        return {
            TARIFFS.TARIFF1: order_info[AlgoField.PRICE_ALONE_TARIFF1],
            TARIFFS.TARIFF2: order_info[AlgoField.PRICE_ALONE_TARIFF2]
        }


def get_offers(request):
    order_settings = OrderSettings.fromRequest(request)

    # TODO_WB: save all searches? in our db? use vision.bi ?
    # TODO_WB: save the requested search params and associate with a push_token from request for later notifications of similar searches
    # TODO_WB: real test for coverage, generate a list of uncovered addresses users tried booking to
    if order_settings.pickup_address.city_name.find(u"תל אביב") < 0 or order_settings.dropoff_address.city_name.find(u"תל אביב") < 0:
        return JSONResponse({'error': u'לא ניתן להזמין לכתובת שנבחרה. אנא נסו שנית בקרוב.'})

    if not order_settings.private:
        candidate_rides = get_candidate_rides(order_settings)
    else:
        candidate_rides = []

    matching_rides = get_matching_rides(candidate_rides, order_settings)

    offers = []
    tariffs = RuleSet.objects.all()

    for ride_data in matching_rides:
        ride_id = ride_data[AlgoField.RIDE_ID]
        ride = SharedRide.by_id(ride_id)

        # get price for offer according to tariff
        price = None
        price_alone = None
        for tariff in tariffs:
            if tariff.is_active(order_settings.pickup_dt.date(), order_settings.pickup_dt.time()):
                price = round(get_order_price_data_from(ride_data).get(tariff.tariff_type), 2)
                price_alone = get_order_price_data_from(ride_data, sharing=False).get(tariff.tariff_type)
                break
        if not price:
            logging.warning("get_offers missing price for %s" % order_settings.pickup_dt)
            continue

        if ride_id == NEW_ORDER_ID:
            offer = {
                "pickup_time": to_js_date(order_settings.pickup_dt),
                "price": price,
                "seats_left": MAX_SEATS,
                "new_ride": True,
                "comment": ""  # TODO_WB: sharing chances
            }

        else:
            time_sharing = ride_data[AlgoField.ORDER_INFOS][str(NEW_ORDER_ID)][AlgoField.TIME_SHARING]
            time_alone = ride_data[AlgoField.ORDER_INFOS][str(NEW_ORDER_ID)][AlgoField.TIME_ALONE]
            time_addition = int((time_sharing - time_alone) / 60)
            price_addition = int(price_alone - price)

            pickup_point = first(lambda p: NEW_ORDER_ID in p[AlgoField.ORDER_IDS] and p[AlgoField.TYPE] == AlgoField.PICKUP, ride_data[AlgoField.RIDE_POINTS])
            ride_orders = ride.orders.all()
            offer = {
                "ride_id": ride_id,
                "pickup_time": to_js_date(ride.depart_time + datetime.timedelta(seconds=pickup_point[AlgoField.OFFSET_TIME])),
                "passengers": [{'name': order.passenger.name, 'picture_url': order.passenger.picture_url} for order in ride_orders for seat in range(order.num_seats)],
                "seats_left": MAX_SEATS - sum([order.num_seats for order in ride_orders]),
                "price": price,
                "new_ride": False,
                "comment": u"%s דקות תוספת זמן / חסכון %s₪" % (time_addition, price_addition)
            }

        offers.append(offer)

    return JSONResponse({'offers': offers})

def get_private_offer(request):
    return get_offers(request)

@csrf_exempt
@passenger_required_no_redirect
def cancel_order(request, passenger):
    """
    Cancel an order. Current status must be APPROVED meaning J5 was successful.
    The billing backend is responsible for not charging (J4) the order.
    """
    response = {'success': False,
                'error': GENERIC_ERROR}

    order = Order.by_id(request.POST.get("order_id"))
    if order and order.passenger == passenger:
        if order.change_status(APPROVED, CANCELLED):
            response = {'success': True,
                        'message': _("Order cancelled")}

    return JSONResponse(response)

@csrf_exempt
def book_ride(request):
    passenger = Passenger.from_request(request)
    result = {
        'status': '',
        'order_id': None,
        'redirect': '',
        'error': '',
        'pickup_dt': None
    }

    if passenger and passenger.user and hasattr(passenger, "billing_info"): # we have logged-in passenger with billing_info - let's proceed
        order_settings = OrderSettings.fromRequest(request)
        request_data = simplejson.loads(request.POST.get('data'))
        ride_id = int(request_data.get("ride_id", NEW_ORDER_ID))

        order_id = create_order(order_settings, passenger, ride_id)

        if order_id is not None:
            order = Order.by_id(order_id)
            result['status'] = 'success'
            result['order_id'] = order_id
            result['pickup_formatted'] = order.from_raw
            result['pickup_dt'] = to_js_date(order.depart_time)
        else:
            result['status'] = 'failed'
            result['error'] = 'Booking failed for some reason'

    else: # not authorized for booking
        if not hasattr(passenger, "billing_info"):
            result['status'] = 'billing_failed'
            result['redirect'] = get_token_url(request) # go to billing
        else:
            result['status'] = 'auth_failed'

    return JSONResponse(result)


def create_order(order_settings, passenger, ride_id):
    ride = SharedRide.by_id(ride_id)

    # get ride data from algo: don't trust the client
    candidates = [ride] if ride else []
    matching_rides = get_matching_rides(candidates, order_settings)
    ride_data = first(lambda match: match[AlgoField.RIDE_ID] == ride_id, matching_rides)

    if not ride_data:
        return None

    order = Order.fromOrderSettings(order_settings, passenger, commit=False)

    if order_settings.private:
        order.type = OrderType.PRIVATE
    else:
        order.type = OrderType.SHARED

    order.price_data = get_order_price_data_from(ride_data)
    order.save()
    logging.info("created new %s order [%s]" % (OrderType.get_name(order.type), order.id))

    billing_trx = BillingTransaction(order=order, amount=order.price, debug=order.debug)
    billing_trx.save()
    billing_trx.commit(callback_args={
        "ride_id": ride_id,
        "ride_data": ride_data
    })

    return order.id

def billing_approved_book_order(ride_id, ride_data, order):
    from sharing.station_controller import send_ride_in_risk_notification

    try:
        if ride_id == NEW_ORDER_ID:
            ride = create_shared_ride_for_order(ride_data, order)
        else:
            ride = SharedRide.by_id(ride_id)
            if ride and ride.lock(): # try joining existing ride
                try:
                    update_ride_for_order(ride, ride_data, order)
                    ride.unlock()
                    #TODO_WB: notify passengers their price dropped

                except Exception, e:
                    #TODO_WB: handle this error in some way - try again, create a new ride
                    logging.error(traceback.format_exc())
                    ride.unlock()

                    raise Exception(e.message)
            else:
                logging.info("ride lock failed: creating a new ride")
                ride = create_shared_ride_for_order(ride_data, order)

    except Exception, e:
        send_ride_in_risk_notification("Failed during post billing processing: %s" % e.message, ride_id)

def create_shared_ride_for_order(ride_data, order):
    ride = SharedRide()
    ride.depart_time = order.depart_time
    ride.debug = order.debug
    ride.arrive_time = ride.depart_time + datetime.timedelta(seconds=ride_data[AlgoField.REAL_DURATION])
    ride.cost_data = get_ride_cost_data_from(ride_data)
    if order.type == OrderType.PRIVATE:
        ride.can_be_joined = False
    ride.save()
    logging.info("created new ride [%s] for order [%s]" % (ride.id, order.id))

    for point_data in ride_data[AlgoField.RIDE_POINTS]:
        create_ride_point(ride, point_data)

    for p in ride.points.all():
        if p.type == StopType.PICKUP:
            order.pickup_point = p
        else:
            order.dropoff_point = p

    order.ride = ride

    order.price_data = get_order_price_data_from(ride_data)
    order.save()

    return ride

def update_ride_for_order(ride, ride_data, new_order, depart_time=None):
    if not depart_time:
        #TODO_WB: decide what is the correct depart time
        depart_time = ride.depart_time

    orders = ride.orders.all()
    new_order_points = {
        AlgoField.PICKUP: None,
        AlgoField.DROPOFF: None
    }

    ride_points_data = ride_data[AlgoField.RIDE_POINTS]

    # update order prices and stop times of existing points
    for order in orders:
        order.price_data = get_order_price_data_from(ride_data, order.id)
        order.save()

        pickup_point = order.pickup_point
        dropoff_point = order.dropoff_point

        for point_data in ride_points_data:
            order_ids = point_data[AlgoField.ORDER_IDS]
            ptype = point_data[AlgoField.TYPE]
            offset = point_data[AlgoField.OFFSET_TIME]

            if order.id in order_ids:
                if ptype == AlgoField.PICKUP:
                    p = pickup_point
                else:
                    p = dropoff_point

                p.stop_time = depart_time + datetime.timedelta(seconds=offset)
                p.save()

                if NEW_ORDER_ID in order_ids:
                    new_order_points[ptype] = p


    # update stop times or create points for the new order
    for point_data in ride_points_data:
        ptype = point_data[AlgoField.TYPE]
        order_ids = point_data[AlgoField.ORDER_IDS]

        if NEW_ORDER_ID in order_ids:
            if len(order_ids) == 1:  # new point
                p = create_ride_point(ride, point_data)
            else:
                p = new_order_points[ptype]

            if p.type == StopType.PICKUP:
                new_order.pickup_point = p
            else:
                new_order.dropoff_point = p

    new_order.ride = ride
    new_order.price_data = get_order_price_data_from(ride_data)
    new_order.save()

    ride.cost_data = get_ride_cost_data_from(ride_data)
    ride.save()


def create_ride_point(ride, point_data):
    point = RidePoint()
    point.type = StopType.PICKUP if point_data[AlgoField.TYPE] == AlgoField.PICKUP else StopType.DROPOFF
    point.lon = point_data[AlgoField.POINT_ADDRESS][AlgoField.LNG]
    point.lat = point_data[AlgoField.POINT_ADDRESS][AlgoField.LAT]
    point.address = point_data[AlgoField.POINT_ADDRESS][AlgoField.NAME]
    point.stop_time = ride.depart_time + datetime.timedelta(seconds=point_data[AlgoField.OFFSET_TIME])
    point.ride = ride
    point.save()

    return point

@csrf_exempt
def track_app_event(request):
    return HttpResponse("OK")

# ==============
# HELPER CLASSES
# ==============
class AddressType(Enum):
    STREET_ADDRESS = 0
    POI = 1


class OrderSettings:
    pickup_address = None # Address instance
    dropoff_address = None # Address instance

    num_seats = 1
    pickup_dt = None # datetime
    luggage = False
    private = False # TODO_WB: replace with order type?
    debug = False

    language_code = settings.LANGUAGE_CODE
    user_agent = None
    mobile = None

    def __init__(self, num_seats=1, pickup_address=None, dropoff_address=None, pickup_dt=None, luggage=False,
                 private=False, debug=False):
        # TODO_WB: add validations
        self.num_seats = num_seats
        self.pickup_address = pickup_address
        self.dropoff_address = dropoff_address
        self.pickup_dt = pickup_dt
        self.luggage = luggage
        self.private = private
        self.debug = debug

    @classmethod
    def fromRequest(cls, request):
        request_data = simplejson.loads(request.REQUEST.get("data"))
        request_data = dict_to_str_keys(request_data)

        pickup = request_data.get("pickup")
        dropoff = request_data.get("dropoff")
        settings = request_data.get("settings")
        asap = request_data.get("asap")

        inst = cls()
        inst.num_seats = int(settings["num_seats"])
        inst.debug = bool(settings["debug"])
        inst.private = bool(settings["private"])
        inst.pickup_address = Address(**pickup)
        inst.dropoff_address = Address(**dropoff)

        if asap:
            inst.pickup_dt = default_tz_now() + datetime.timedelta(minutes=ASAP_BOOKING_TIME)
            logging.info("ASAP set as %s" % inst.pickup_dt.strftime("HH:MM"))
        else:
            inst.pickup_dt = dateutil.parser.parse(request_data.get("pickup_dt"))

        inst.mobile = request.mobile
        inst.language_code = request.POST.get("language_code", get_language_from_request(request))
        inst.user_agent = request.META.get("HTTP_USER_AGENT")

        return inst

    def serialize(self):
        return {
            "from_address": self.pickup_address.formatted_address,
            "from_lat": self.pickup_address.lat,
            "from_lon": self.pickup_address.lng,
            "to_address": self.dropoff_address.formatted_address,
            "to_lat": self.dropoff_address.lat,
            "to_lon": self.dropoff_address.lng,
            "num_seats": self.num_seats,
            "id": NEW_ORDER_ID
        }


class Address:
    lat = 0.0
    lng = 0.0
    house_number = None
    street = ""
    city_name = ""
    country_code = ""
    description = ""
    address_type = None

    def __init__(self, lat, lng, house_number=None, street=None, city_name=None, description=None, country_code=None,
                 address_type=AddressType.STREET_ADDRESS, **kwargs):
        self.lat = float(lat)
        self.lng = float(lng)

        self.house_number = house_number
        self.street = street
        self.city_name = city_name
        self.description = description
        self.country_code = country_code
        self.address_type = address_type

    @classmethod
    def from_order(cls, order, address_type):
        new_address = None
        try:
            new_address = Address(
                        getattr(order, "%s_lat" % address_type),
                        getattr(order, "%s_lon" % address_type),
                        house_number=getattr(order, "%s_house_number" % address_type),
                        street=getattr(order, "%s_street_address" % address_type),
                        city_name=getattr(order, "%s_city" % address_type).name,
                        description=getattr(order, "%s_raw" % address_type),
                        country_code=getattr(order, "%s_country" % address_type).code
                    )
        except AttributeError, e:
            pass
        return new_address


    @property
    def formatted_address(self):
        return u"%s %s, %s" % (self.street, self.house_number, self.city_name)

    def __eq__(self, other):
        return self.__hash__() == other.__hash__()

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return self.formatted_address.__hash__()

