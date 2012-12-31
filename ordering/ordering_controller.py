# -*- coding: utf-8 -*-
from __future__ import absolute_import # we need absolute imports since ordering contains pricing.py

import logging
import traceback
import urllib
from django.core.urlresolvers import reverse
from django.views.decorators.csrf import csrf_exempt
from google.appengine.api import memcache
from google.appengine.ext import deferred
from analytics.models import BIEvent, BIEventType, SearchRequest, RideOffer
from billing.billing_manager import  get_token_url
from billing.enums import BillingStatus
from billing.models import BillingTransaction
from common.models import Counter
from common.tz_support import to_js_date, default_tz_now, utc_now, ceil_datetime, trim_seconds, TZ_INFO, TZ_JERUSALEM
from common.util import first, Enum, dict_to_str_keys, datetimeIterator, get_uuid
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from django.conf import settings
from django.views.decorators.cache import never_cache
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseBadRequest
from django.utils.translation import ugettext_lazy, get_language_from_request, ugettext as _
from djangotoolbox.http import JSONResponse
from oauth2.views import update_profile_fb
from ordering.decorators import  passenger_required_no_redirect
from ordering.enums import RideStatus
from ordering.models import SharedRide, RidePoint, StopType, Order, OrderType, ACCEPTED, APPROVED, Passenger, CHARGED, CANCELLED, CURRENT_BOOKING_DATA_KEY
from ordering.signals import order_price_changed_signal
from ordering.passenger_controller import get_position_for_order
from pricing.functions import get_discount_rules_and_dt
from pricing.models import  RuleSet, DiscountRule
from sharing.algo_api import NEW_ORDER_ID
from sharing.signals import ride_deleted_signal
import simplejson
import datetime
import dateutil.parser
import sharing.algo_api as algo_api


WAYBETTER_STATION_NAME = "WAYbetter"
CLOSE_CHILD_BROWSER_URI = "https://waybetter-app.appspot.com"

DISCOUNTED_OFFER_PREFIX = "fjsh34897dfasg3478o5"
DISCOUNTED_OFFERS_NS = "DISCOUNTED_OFFERS"

MAX_SEATS = 3
MAX_RIDE_DURATION = 20 #minutes

OFFERS_TIMEDELTA = datetime.timedelta(hours=2)

ORDER_SUCCESS_STATUS = [APPROVED, ACCEPTED, CHARGED]

PREVIOUS_RIDES_TO_DISPLAY = 10
HISTORY_SUGGESTIONS_TO_SEARCH = 30

GENERIC_ERROR = _("Your request could not be completed.")

def booking_interval():
    # 2012 SYLVESTER
    if datetime.datetime(2012, 12, 31, 20, 00, tzinfo=TZ_JERUSALEM) <= default_tz_now() <= datetime.datetime(2013, 1, 1, 5, 30, tzinfo=TZ_JERUSALEM):
        return 30  # minutes

    return 10  # minutes

def asap_interval():
    # 2012 SYLVESTER
    if datetime.datetime(2012, 12, 31, 20, 00, tzinfo=TZ_JERUSALEM) <= default_tz_now() <= datetime.datetime(2013, 1, 1, 5, 30, tzinfo=TZ_JERUSALEM):
        return 30  # minutes

    return 10 # minutes

def staff_m2m(request):
    return render_to_response("staff_m2m.html", RequestContext(request))

def home(request, suggest_apps=True):
    user_agent_lower = request.META.get("HTTP_USER_AGENT", "").lower()
    is_android =  user_agent_lower.find("android") > -1
    is_ios =  user_agent_lower.find("iphone") > -1
    lib_ng = True

    total_orders = Counter.objects.get(name="total_orders")
    money_saved = Counter.objects.get(name="money_saved")

    suggest_apps = (is_android or is_ios) and suggest_apps
    if suggest_apps:
        return render_to_response('mobile/suggest_apps.html', locals(), context_instance=RequestContext(request))

    return render_to_response('wb_home.html', locals(), context_instance=RequestContext(request))


def booking_page(request, continued=False):
    lib_ng = True
    lib_map = True
    lib_geo = True

    if continued:
        continue_booking = simplejson.dumps(True)
    else:
        request.session[CURRENT_BOOKING_DATA_KEY] = None

    BIEvent.log(BIEventType.BOOKING_START, request=request, passenger=Passenger.from_request(request))

    return render_to_response("booking_page.html", locals(), RequestContext(request))


def get_ongoing_ride_details(request):
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

        taxi_position = get_position_for_order(order)
        if taxi_position:
            taxi_position = {"lat": taxi_position.lat, "lng": taxi_position.lon}

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
            "taxi_position"     : taxi_position,
            "taxi_number"       : ride.taxi_number,
            "pickup_position"   : pickup_position,
            "dropoff_position"  : dropoff_position,
            'passenger_picked_up': order.pickup_point.visited,
            "stops"             : stops,
            "empty_seats"       : MAX_SEATS - sum([o.num_seats for o in sorted_orders]),
        }
    else:
        logging.error("ongoing ride details error for order [%s]" % order_id)

    return JSONResponse(response)


def get_ongoing_order(passenger):
    """
    @param passenger:
    @return: ongoing order or None
    """
    ongoing_order = None

    # orders that can still be ongoing
    recently = default_tz_now() - datetime.timedelta(minutes=MAX_RIDE_DURATION)
    possibly_ongoing_orders = passenger.orders.filter(depart_time__gt=recently).order_by("-depart_time")
    for order in possibly_ongoing_orders:
        if all([ order.status in ORDER_SUCCESS_STATUS,
                 order.ride and order.ride.status == RideStatus.ACCEPTED,
                 order.dropoff_point and not order.dropoff_point.visited ]):

            ongoing_order = order
            break

    return ongoing_order

@never_cache
def sync_app_state(request):
    earliest_pickup_time = ceil_datetime(trim_seconds(default_tz_now()) + datetime.timedelta(minutes=asap_interval()), minutes=booking_interval())
    latest_pickup_time = earliest_pickup_time + datetime.timedelta(hours=(24*14))
    dt_options = list(datetimeIterator(earliest_pickup_time, latest_pickup_time, delta=datetime.timedelta(minutes=booking_interval())))

    response = {
        "logged_in": request.user.is_authenticated(),
        "pickup_datetime_options": [to_js_date(opt) for opt in dt_options],
        "pickup_datetime_default_idx": 0,
        "asap_as_default": True,
        "booking_data": request.session.get(CURRENT_BOOKING_DATA_KEY)
    }

    passenger = Passenger.from_request(request)
    response["show_url"] = "" # change to cause child browser to open with passed url

    if passenger:
        response["authenticated"] = True
        response["passenger_picture_url"] = passenger.picture_url

        ongoing_order = get_ongoing_order(passenger)
        if ongoing_order:
            response["ongoing_order_id"] = ongoing_order.id

        future_orders = get_future_orders_for(passenger)
        response["future_orders_count"] = len(future_orders)

    trimed_response = response.copy()
    trimed_response['pickup_datetime_options'] = response['pickup_datetime_options'][:9] + ['...']
    logging.info("get_initial_status: %s" % trimed_response)

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
            response['error'] = _("This card cannot be charged. It may be expired, blocked or not yet supported by WAYbetter (American Express)")
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
    next = request.GET.get("next")  # where to go after process is done

    callback_url = "http://%s%s" % (settings.DEFAULT_DOMAIN, reverse(update_profile_fb, args=[passenger.id, next]))
    fb_url = "%s?client_id=%s&redirect_uri=%s&scope=email" % (settings.FACEBOOK_CONNECT_URI, settings.FACEBOOK_APP_ID, callback_url)
    return JSONResponse({'redirect': fb_url})


def fb_share(request):
    context = request.GET.get("context")
    data = simplejson.loads(request.GET.get("data", ""))
    logging.info("fb share context %s" % context)
    logging.info("fb share data %s" % data)

    caption = u"הצטרפו למהפכת המוניות המשותפות WAYbetter:"
    description = u"מתקדם יותר, חכם יותר, נוח יותר ומשתלם הרבה יותר!"

    if context == 'order_approved':
        order = Order.by_id(data.get('order_id'))
        savings = order.price - order.get_billing_amount()

        if savings:
            caption = u"חסכתי %s₪ על מונית משותפת מ%s ל%s. תצטרפו אלי ונחסוך יחד יותר..." % (savings, order.from_raw, order.to_raw)
        else:
            caption = u"הזמנתי מונית משותפת מ%s ל%s. תצטרפו אלי ונחסוך יחד יותר..." % (order.from_raw, order.to_raw)

    args = {
        'app_id': settings.FACEBOOK_APP_ID,
        'link': settings.DEFAULT_DOMAIN,
        'picture': 'http://%s/static/images/fb_share_logo.png' % settings.DEFAULT_DOMAIN,
        'name': 'WAYbetter',
        'caption': caption.encode("utf-8"),
        'description': description.encode("utf-8"),
        'redirect_uri': CLOSE_CHILD_BROWSER_URI if request.mobile else "http://%s" % settings.DEFAULT_DOMAIN,
        'display': 'touch' if request.mobile else 'page'
    }
    url = "http://%s.facebook.com/dialog/feed?%s" % ("m" if request.mobile else "www", urllib.urlencode(args))

    return HttpResponseRedirect(url)


@never_cache
@passenger_required_no_redirect
def get_history_suggestions(request, passenger):
    orders = passenger.orders.order_by('-depart_time')[:HISTORY_SUGGESTIONS_TO_SEARCH]
    orders = filter(lambda o: o.type != OrderType.PICKMEAPP, orders)

    addresses = []
    for order in orders:
        address = Address.from_order(order, "from")
        if address not in addresses:
            addresses.append(address)

        address = Address.from_order(order, "to")
        if address not in addresses:
            addresses.append(address)

    data = [a.__dict__ for a in addresses]
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
        ride_mates = [{'name': mate_order.passenger.name, 'picture_url': mate_order.passenger.picture_url}
                                    for mate_order in ride_mates_orders for seat in range(order.num_seats)]

        dispatching_event = first(lambda e: e.taxi_id, ride.events.all())

        ride_data = {
            "order_id": order.id,
            "pickup_time": to_js_date(order.pickup_point.stop_time),
            "passengers": ride_mates,
            "seats_left": MAX_SEATS - sum([o.num_seats for o in ride_orders]),
            "your_seats": order.num_seats,
            "taxi_number": dispatching_event.taxi_id if dispatching_event else None,
            "station_name": ride.station.name if ride.station else WAYBETTER_STATION_NAME,
            "price": order.get_billing_amount(),
            "price_alone": order.price_alone,
            "billing_status": ugettext_lazy(order.get_status_display().title()),
            "pickup": order.from_raw,
            "dropoff": order.to_raw,
            "is_private": order.type == OrderType.PRIVATE,
            "comment": ""
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
            "seats_left": MAX_SEATS - sum([o.num_seats for o in ride_orders]),
            "your_seats": order.num_seats,
            "price": order.get_billing_amount(),
            "price_alone": order.price_alone,
            "is_private": order.type == OrderType.PRIVATE,
            "pickup": order.from_raw,
            "dropoff": order.to_raw,
            "billing_status": _("or less"),
            "comment": ""
        }

        data.append(ride_data)

    return JSONResponse(data)

def get_future_orders_for(passenger):
    future_order_qs = passenger.orders.filter(
        depart_time__gte=utc_now(), status__in=ORDER_SUCCESS_STATUS, type__in=[OrderType.PRIVATE, OrderType.SHARED]).order_by('-depart_time')
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

    candidates = SharedRide.objects.filter(depart_time__gt=earliest, depart_time__lte=latest)
    candidates = filter(lambda candidate: is_valid_candidate(candidate, order_settings), candidates)

    return candidates


def is_valid_candidate(ride, order_settings):
    return ride.debug == settings.DEV and \
           ride.can_be_joined and \
           ride.depart_time > default_tz_now() + datetime.timedelta(minutes=asap_interval()) and \
           ride.status in [RideStatus.PENDING, RideStatus.ASSIGNED] and \
           sum([order.num_seats for order in ride.orders.all()]) + order_settings.num_seats <= MAX_SEATS


def get_matching_rides(candidate_rides, order_settings):
    """
    Get matching rides for the given order_settings out of the candidate_rides

    @param candidate_rides:
    @param order_settings:
    @return: A list of RideData objects representing modified SharedRides
    """

    matches = algo_api.find_matches(candidate_rides, order_settings)
    return matches

def get_offers(request):
    order_settings = OrderSettings.fromRequest(request)

    # TODO_WB: save the requested search params and associate with a push_token from request for later notifications of similar searches

    if not order_settings.private:
        candidate_rides = get_candidate_rides(order_settings)
        look_for_discounts = True
    else:
        candidate_rides = []
        look_for_discounts = False

    matching_rides = get_matching_rides(candidate_rides, order_settings)
    if not matching_rides:
        return JSONResponse({'error': u'לא ניתן להזמין לכתובת שנבחרה. אנא נסו שנית בקרוב.'})

    offers = []

    start_ride_algo_data = None

    for ride_data in matching_rides:
        ride_id = ride_data.ride_id
        ride = SharedRide.by_id(ride_id)

        # get price for offer according to tariff
        tariff = RuleSet.get_active_set(order_settings.pickup_dt)
        price = ride_data.order_price(NEW_ORDER_ID, tariff)
        price_alone = ride_data.order_price(NEW_ORDER_ID, tariff, sharing=False)

        if not price > 0:
            logging.warning("get_offers missing price for %s" % order_settings.pickup_dt)
            continue

        if ride_id == NEW_ORDER_ID:  # start a new ride
            start_ride_algo_data = ride_data
            offer = {
                "asap": order_settings.asap,
                "pickup_time": to_js_date(order_settings.pickup_dt),
                "price": price,
                "seats_left": MAX_SEATS,
                "new_ride": True,
                "comment": u"הזמן ראשון ואחרים יצטרפו אליך"  # TODO_WB: sharing chances
            }

        else:  # sharing offers
            time_sharing = ride_data.order_time(NEW_ORDER_ID)
            time_alone = ride_data.order_time(NEW_ORDER_ID, sharing=False)
            time_addition = int((time_sharing - time_alone) / 60)

            pickup_point = ride_data.order_pickup_point(NEW_ORDER_ID)
            ride_orders = ride.orders.all()
            pickup_time = compute_new_departure(ride, ride_data) + datetime.timedelta(seconds=pickup_point.offset)
            if pickup_time < default_tz_now() + datetime.timedelta(minutes=asap_interval()):
                logging.info("skipping offer because pickup_time is too soon: %s" % pickup_time)
                continue

            offer = {
                "ride_id": ride_id,
                "pickup_time": to_js_date(pickup_time),
                "passengers": [{'name': order.passenger.name, 'picture_url': order.passenger.picture_url} for order in ride_orders for seat in range(order.num_seats)],
                "seats_left": MAX_SEATS - sum([order.num_seats for order in ride_orders]),
                "price": price,
                "new_ride": False,
                "comment": u"תוספת זמן: %s דקות / חסכון של %s₪ או יותר" % (time_addition, "%g" % (price_alone - price))
            }

            # good enough offer found, no discounts
            if order_settings.pickup_dt - datetime.timedelta(minutes=30) < pickup_time < order_settings.pickup_dt + datetime.timedelta(minutes=30):
                look_for_discounts = False

        offers.append(offer)

    # add discounted offers if relevant

    ## override
    look_for_discounts = True
    ## override

    if look_for_discounts and start_ride_algo_data:
        offers += get_discounted_offers(request, order_settings, start_ride_algo_data)

    offers = sorted(offers, key=lambda  o: o["pickup_time"], reverse=False)

    deferred.defer(save_search_req_and_offers, Passenger.from_request(request), order_settings, offers)
    return JSONResponse({'offers': offers})


def get_discounted_offers(request, order_settings, start_ride_algo_data):
    discounted_offers = []

    user_email_domain = None
    if request.user.is_authenticated() and request.user.email:
        user_email_domain = request.user.email.split("@")[1]

    logging.info("get discounted offers @%s" % user_email_domain)

    earliest_offer_dt = ceil_datetime(max(trim_seconds(default_tz_now()) + datetime.timedelta(minutes=asap_interval()), order_settings.pickup_dt - OFFERS_TIMEDELTA), minutes=booking_interval())
    discount_dts_tuples = get_discount_rules_and_dt(order_settings, earliest_offer_dt, order_settings.pickup_dt + OFFERS_TIMEDELTA, datetime.timedelta(minutes=booking_interval()))

    for discount_rule, discount_dt in discount_dts_tuples:
        if discount_rule.email_domains and (user_email_domain not in discount_rule.email_domains):
            logging.info(u"skipping: %s - only for %s" % (discount_rule.name, ", ".join(discount_rule.email_domains)))
            continue

        tariff_for_discount_offer = RuleSet.get_active_set(discount_dt)
        base_price_for_discount_offer = start_ride_algo_data.order_price(NEW_ORDER_ID, tariff_for_discount_offer)
        if base_price_for_discount_offer:
            discount = discount_rule.get_discount(base_price_for_discount_offer)
            if discount == 0:
                logging.info(u"skipping %s: grants zero discount" % discount_rule.name)
                continue

            offer_key = "%s_%s" % (DISCOUNTED_OFFER_PREFIX, get_uuid())
            memcache.set(offer_key, {'discount_rule_id': discount_rule.id, 'pickup_dt': discount_dt}, namespace=DISCOUNTED_OFFERS_NS)

            offer_text = u"הזמן ראשון וקבל ₪%g הנחה מובטחת" % discount
            if discount_rule.offer_text:
                offer_text = discount_rule.offer_text
                if offer_text.find("%g") > -1:  # render discount amount
                    offer_text %= discount

            discount_offer_data = {
                "ride_id": offer_key,
                "pickup_time": to_js_date(discount_dt),
                "discount_picture_url": discount_rule.picture_url,
                "discount_name": discount_rule.display_name,
                "passengers": [],
                "seats_left": MAX_SEATS,
                "price": base_price_for_discount_offer - discount,
                "new_ride": True,  # disguise as an exisiting ride
                "comment": offer_text
            }

            if not request.META.get("HTTP_USER_AGENT", "").startswith("WAYbetter/iPhone/1.2.1"):  # only for client < 1.2.1
                discount_offer_data.update({
                    "seats_left": MAX_SEATS - 1,
                    "passengers": [{'name': discount_rule.display_name, 'picture_url': discount_rule.picture_url}]
                })

            discounted_offers.append(discount_offer_data)

    return discounted_offers


def save_search_req_and_offers(passenger, order_settings, offers):
    sr = SearchRequest.fromOrderSettings(order_settings, passenger)
    sr.save()

    for offer in offers:
        pickup_dt = offer['pickup_time'] / 1000
        pickup_dt = datetime.datetime.fromtimestamp(pickup_dt).replace(tzinfo=TZ_INFO["UTC"]).astimezone(TZ_INFO['Asia/Jerusalem'])
        ride_offer = RideOffer(search_req=sr, ride_key=offer.get('ride_id'), ride=SharedRide.by_id(offer.get('ride_id')), pickup_dt=pickup_dt, seats_left=offer['seats_left'], price=offer['price'], new_ride=offer['new_ride'])

        if str(offer.get('ride_id')).startswith(DISCOUNTED_OFFER_PREFIX):
            discounted_offer = memcache.get(offer.get('ride_id'), namespace=DISCOUNTED_OFFERS_NS)
            discount_rule = DiscountRule.by_id(discounted_offer["discount_rule_id"])
            if discount_rule:
                ride_offer.discount_rule = discount_rule
                ride_offer.new_ride = True # this is actually a new ride

        ride_offer.save()


def get_private_offer(request):
    res = get_offers(request)
    content = simplejson.loads(res.content)
    if 'error' in content:
        return HttpResponseBadRequest(content['error'])
    else:
        return res

@csrf_exempt
@passenger_required_no_redirect
def cancel_order(request, passenger):
    """
    Cancel an order. Current status must be APPROVED meaning J5 was successful.
    The billing backend is responsible for not charging (J4) the order.
    """
    from sharing.sharing_dispatcher import WS_SHOULD_HANDLE_TIME
    response = {'success': False,
                'message': _("This order cannot be cancelled anymore")}

    order = Order.by_id(request.POST.get("order_id"))
    cancel_allowed = False
    if order and order.passenger == passenger:
        cancel_allowed = True
        ride = order.ride
        if ride:
            cancel_allowed = ride.depart_time > default_tz_now() + datetime.timedelta(minutes=WS_SHOULD_HANDLE_TIME)

    if cancel_allowed and order.change_status(APPROVED, CANCELLED):
        response = {'success': True,
                    'message': _("Order cancelled")}

    return JSONResponse(response)

@csrf_exempt
def book_ride(request):
    passenger = Passenger.from_request(request)
    request_data = simplejson.loads(request.POST.get('data'))
    logging.info(u"book ride: %s\n%s" % (passenger, unicode(simplejson.dumps(request_data), "unicode-escape")))

    result = {
        'status': '',
        'order_id': None,
        'redirect': '',
        'error': '',
        'pickup_dt': None
    }

    if passenger and passenger.user and hasattr(passenger, "billing_info"): # we have logged-in passenger with billing_info - let's proceed
        order_settings = OrderSettings.fromRequest(request)
        ride_id = request_data.get("ride_id")

        new_ride = (ride_id == NEW_ORDER_ID)
        discounted_ride = (ride_id and str(ride_id).startswith(DISCOUNTED_OFFER_PREFIX))

        join_ride = not (new_ride or discounted_ride)
        ride_to_join = SharedRide.by_id(ride_id) if join_ride else None

        order = None
        if ride_to_join:  # check it is indeed a valid candidate
            if is_valid_candidate(ride_to_join, order_settings):
                order = create_order(order_settings, passenger, ride=ride_to_join)
            else:
                logging.warning("tried booking an invalid ride candidate")
                result['error'] = _("Sorry, but this ride has been closed for booking")

        else:  # new or discounted ride, check pickup time isn't before ASAP (minus a couple seconds to allow booking to exactly ASAP)
            if order_settings.pickup_dt <= default_tz_now() + datetime.timedelta(minutes=asap_interval()) - datetime.timedelta(seconds=10):
                logging.warning("tried booking to expired pickup time %s" % order_settings.pickup_dt)
                result['error'] = _("Please choose a later pickup time")
            else:
                if discounted_ride:
                    discounted_offer = memcache.get(ride_id, namespace=DISCOUNTED_OFFERS_NS)
                    order = create_order(order_settings, passenger, discounted_offer=discounted_offer)
                else:
                    order = create_order(order_settings, passenger)


        if order:
            result['status'] = 'success'
            result['order_id'] = order.id
            result['pickup_formatted'] = order.from_raw
            result['pickup_dt'] = to_js_date(order.depart_time)
            result["price"] = order.get_billing_amount()

            ride_orders = [order] + ( list(ride_to_join.orders.all()) if ride_to_join else [] )
            result["passengers"] = [{'name': o.passenger.name, 'picture_url': o.passenger.picture_url, 'is_you': o==order} for o in ride_orders for seat in range(o.num_seats)]
            result["seats_left"] = MAX_SEATS - sum([o.num_seats for o in ride_orders])

            deferred.defer(join_offer_and_order, order, request_data)

        else:
            result['status'] = 'failed'

    else:  # not authorized for booking, save current booking state in session
        set_current_booking_data(request)

        if passenger and not hasattr(passenger, "billing_info"):
            result['status'] = 'billing_failed'
            result['redirect'] = get_token_url(request) # go to billing
        else:
            result['status'] = 'auth_failed'

    logging.info("book ride result: %s" % result)
    return JSONResponse(result)

def join_offer_and_order(order, request_data):
    # connect the order the the offer that was clicked
    offer_ride_key = request_data.get("ride_id")
    logging.info("join_offer_and_order: offer_ride_key = '%s'" % offer_ride_key)

    last_search_req = SearchRequest.objects.filter(passenger=order.passenger).order_by("-create_date")
    if last_search_req: # ok, search was performed by a logged-in passenger
       offers = last_search_req[0].offers.all()
       for offer in offers:
           logging.info("checking offer [%s]: '%s'" % (offer.id, offer.ride_key))
           if offer.ride_key == (str(offer_ride_key) if offer_ride_key else None):
               logging.info("offer %s was joined with order %s" % (offer.id, order.id))
               offer.order = order
               offer.save()
               break

    else:
        logging.warning("search request was done anonymously, can't attach offer to order")

@csrf_exempt
def set_current_booking_data(request):
    request_data = simplejson.loads(request.POST.get('data'))
    request.session[CURRENT_BOOKING_DATA_KEY] = request_data
    logging.info("set booking data")

    return HttpResponse("OK")

def create_order(order_settings, passenger, ride=None, discounted_offer=None):
    """
    Returns a created Order or None
    """
    ride_id = ride.id if ride else NEW_ORDER_ID

    # get ride data from algo: don't trust the client
    candidates = [ride] if ride else []
    matching_rides = get_matching_rides(candidates, order_settings)
    ride_data = first(lambda match: match.ride_id == ride_id, matching_rides)

    if not ride_data:
        return None

    order = Order.fromOrderSettings(order_settings, passenger, commit=False)

    if ride:  # if joining a ride, order departure is as shown in offer, not what was submitted in order_settings
        ride_departure = compute_new_departure(ride, ride_data)
        new_order_pickup_point = ride_data.order_pickup_point(NEW_ORDER_ID)
        order.depart_time = ride_departure + datetime.timedelta(seconds=new_order_pickup_point.offset)

    if order_settings.private:
        order.type = OrderType.PRIVATE
    else:
        order.type = OrderType.SHARED

    order.price_data = ride_data.order_price_data(NEW_ORDER_ID)
    if discounted_offer:
        discount_rule = DiscountRule.by_id(discounted_offer["discount_rule_id"])
        order.depart_time = discounted_offer["pickup_dt"]
        if discount_rule and discount_rule.is_active_at(order.depart_time, order_settings.pickup_address, order_settings.dropoff_address):
            discount = discount_rule.get_discount(order.price)
            logging.info(u"discount rule %s granting discount %s" % (discount_rule.name, discount))
            order.discount = discount
            order.discount_rule = discount_rule
        else:
            logging.error("Expected a discount but discount doesn't exist or isn't active")
            return None

    order.save()
    logging.info("created new %s order [%s]" % (OrderType.get_name(order.type), order.id))

    billing_trx = BillingTransaction(order=order, amount=order.get_billing_amount(), debug=order.debug)
    billing_trx.save()
    billing_trx.commit(callback_args={
        "ride_id": ride_id,
        "ride_data": ride_data
    })

    return order

def billing_approved_book_order(ride_id, ride_data, order):
    from sharing.station_controller import send_ride_in_risk_notification

    try:
        if ride_id == NEW_ORDER_ID:
            ride = create_shared_ride_for_order(ride_data, order)
        else:
            ride = SharedRide.by_id(ride_id)
            if ride and ride.lock(): # try joining existing ride
                try:
                    update_ride_add_order(ride, ride_data, order)
                    ride.unlock()

                except Exception, e:
                    #TODO_WB: handle this error in some way - try again, create a new ride
                    logging.error(traceback.format_exc())
                    ride.unlock()

                    raise Exception(e.message)
            else:
                logging.info("ride lock failed: creating a new ride")
                ride = create_shared_ride_for_order(ride_data, order)

    except Exception, e:
        logging.error(traceback.format_exc())
        send_ride_in_risk_notification("Failed during post billing processing: %s" % e.message, ride_id)

def create_shared_ride_for_order(ride_data, order):
    logging.info(u"creating shared ride from ride_data %s" % ride_data)

    ride = SharedRide()
    ride.debug = order.debug
    ride.depart_time = order.depart_time
    ride.arrive_time = order.depart_time + datetime.timedelta(seconds=ride_data.duration)
    ride.distance = ride_data.distance
    ride.cost_data =  ride_data.cost_data
    if order.type == OrderType.PRIVATE:
        ride.can_be_joined = False
    ride.save()

    for point_data in ride_data.points:
        create_ride_point(ride, point_data)

    for p in ride.points.all():
        if p.type == StopType.PICKUP:
            order.pickup_point = p
        else:
            order.dropoff_point = p

    order.ride = ride

    order.price_data = ride_data.order_price_data(NEW_ORDER_ID)
    order.save()

    logging.info("created new ride [%s] for order [%s]" % (ride.id, order.id))

    return ride

def update_ride_add_order(ride, ride_data, new_order):
    # important:
    # connect new_order to ride ONLY AFTER update_ride is done.
    # If not, new_order will turn up in ride.orders.all() queries which doesn't reflect the state of the ride prior to joining

    update_ride(ride, ride_data, new_order=new_order)

    # create or update points for the new order
    for point_data in [ride_data.order_pickup_point(NEW_ORDER_ID), ride_data.order_dropoff_point(NEW_ORDER_ID)]:
        if len(point_data.order_ids) == 1:  # new point
            point = create_ride_point(ride, point_data)

        else:  # find existing point
            existing_order_id = first(lambda id: id != NEW_ORDER_ID, point_data.order_ids)
            existing_order = Order.by_id(existing_order_id)
            point = existing_order.pickup_point if point_data.stop_type == StopType.PICKUP else existing_order.dropoff_point
            logging.info("joining existing point %s" % point.id)

        if point_data.stop_type == StopType.PICKUP:
            new_order.pickup_point = point
        else:
            new_order.dropoff_point = point

    new_order.price_data = ride_data.order_price_data(NEW_ORDER_ID)
    new_order.ride = ride
    new_order.save()


def update_ride_remove_order(order):
    ride = order.ride
    logging.info("remove order[%s] from ride[%s]" % (order.id, ride.id))

    pickup_point = order.pickup_point
    dropoff_point = order.dropoff_point
    order.ride = None
    order.pickup_point = None
    order.dropoff_point = None
    order.save()
    logging.info("order detached, ride now has %s orders" % ride.orders.count())

    if pickup_point.orders.count() == 0:
        pickup_point.delete()
        logging.info("order [%s] pickup point deleted" % order.id)

    if dropoff_point.orders.count() == 0:
        dropoff_point.delete()
        logging.info("order [%s] dropoff point deleted" % order.id)

    if ride.orders.count() == 0:
        logging.info("ride[%s] deleted: last order cancelled" % ride.id)
        ride.delete()
        ride_deleted_signal.send(sender="update_ride_remove_order", ride=ride)
    else:
        ride_data = algo_api.recalc_ride(ride.orders.all())
        update_ride(ride, ride_data)


def update_ride(ride, ride_data, new_order=None):
    """
    Update a SharedRide when passengers join or leave.
    What is updated: distance, cost, depart time, price for each Order and stop times for its RidePoints.

    @param ride      :  The SharedRide to update.
    @param ride_data :  A RideData instance containing the updated data for the ride.
                        In case new_order is passed we assume it is referred to with NEW_ORDER_ID
    @param new_order :  None or the order joining. We assume it NOT POINTING to the ride - isn't returned when calling ride.orders.all()
    """
    depart_time = compute_new_departure(ride, ride_data)
    for order in ride.orders.all():
        # update stop times TODO_WB: notify passengers when pickup times change?
        new_pickup_time = depart_time + datetime.timedelta(seconds=ride_data.order_pickup_point(order.id).offset)
        new_dropoff_time = depart_time + datetime.timedelta(seconds=ride_data.order_dropoff_point(order.id).offset)

        logging.info("updating stop times for order [%s]:\n" \
                     "pickup time %s -> %s\n" \
                     "dropoff time %s -> %s" % (order.id, order.pickup_point.stop_time, new_pickup_time, order.dropoff_point.stop_time, new_dropoff_time))

        order.pickup_point.update(stop_time=new_pickup_time)
        order.dropoff_point.update(stop_time=new_dropoff_time)

        # update prices
        old_billing_amount = order.get_billing_amount()
        order.price_data = ride_data.order_price_data(order.id)  # sets new order.price

        if order.price <= old_billing_amount:  # if algo got a better deal for this user then this will be what he pays
            order.discount = None
        else:  #  update discount so that user doesn't pay more than promised
            order.discount = order.price - old_billing_amount

        order.save()

        if new_order and order.get_billing_amount() < old_billing_amount:  # we need a new_order for the joined passenger name
            order_price_changed_signal.send(sender="update_ride_add_order", order=order, joined_passenger=new_order.passenger, old_price=old_billing_amount, new_price=order.get_billing_amount())


    ride.update(depart_time=depart_time,
                arrive_time=depart_time + datetime.timedelta(seconds=ride_data.duration),
                distance=ride_data.distance,
                cost_data=ride_data.cost_data)

    # The station executing the ride may change: mark the ride as pending so it will be re-dispatched.
    # For example, if someone from newcity joins a ride assigned to an oldcity station, we need to find a newcity station
    ride.change_status(new_status=RideStatus.PENDING)

def create_ride_point(ride, point_data, depart_time=None):
    """
    @param depart_time: ride depart time to compute offsets from
    """
    if not depart_time:
        depart_time = ride.depart_time

    point = RidePoint()
    point.type = point_data.stop_type

    point.lon = point_data.lon
    point.lat = point_data.lat
    point.address = point_data.address
    point.city_name= point_data.city_name

    point.stop_time = depart_time + datetime.timedelta(seconds=point_data.offset)
    point.ride = ride
    point.save()

    logging.info("created new ride point [%s]" % point.id)
    return point


def compute_new_departure(ride, ride_data):
    """
    Compute new depart time so that the first pickup time doesn't change; i.e. ride departs earlier if needed.
    """
    current_departure_time = ride.depart_time
    first_pickup_order = ride.first_pickup.orders.all()[0]

    first_order_pickup_point = ride_data.order_pickup_point(first_pickup_order.id)
    new_departure_time = current_departure_time - datetime.timedelta(seconds=first_order_pickup_point.offset)

    logging.info("ride [%s] departure calc: %s <-- %s" % (ride.id, new_departure_time, current_departure_time))
    return new_departure_time


@csrf_exempt
def track_app_event(request):
    event_name = request.POST.get("name")
    logging.info("Track app event: %s" % event_name)

    passenger = Passenger.from_request(request)
    if event_name:
        if event_name == "APPLICATION_INSTALL":
            BIEvent.log(BIEventType.APP_INSTALL, request=request, passenger=passenger)
        elif event_name == "APPLICATION_OPEN":
            BIEvent.log(BIEventType.BOOKING_START, request=request, passenger=passenger)

    return HttpResponse("OK")

# ==============
# HELPER CLASSES
# ==============

class OrderSettings:
    pickup_address = None # Address instance
    dropoff_address = None # Address instance

    num_seats = 1
    asap = False
    pickup_dt = None # datetime
    luggage = 0
    private = False # TODO_WB: replace with order type?
    debug = False

    language_code = settings.LANGUAGE_CODE
    user_agent = None
    mobile = None

    def __init__(self, num_seats=1, pickup_address=None, dropoff_address=None, asap=False, pickup_dt=None, luggage=0,
                 private=False, debug=False):
        # TODO_WB: add validations
        self.num_seats = num_seats
        self.pickup_address = pickup_address
        self.dropoff_address = dropoff_address
        self.asap = asap
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
        booking_settings = request_data.get("settings")
        asap = request_data.get("asap")


        inst = cls()
        inst.debug = settings.DEV
        inst.num_seats = int(booking_settings["num_seats"])
        inst.luggage = int(booking_settings["luggage"])
        inst.private = bool(booking_settings["private"])
        inst.pickup_address = Address(**pickup)
        inst.dropoff_address = Address(**dropoff)

        # TODO_WB: save extra data when pickup/dropoff have place_id field
        logging.info("pickup_place_id: %s" % pickup.get("place_id"))
        logging.info("dropoff_place_id: %s" % dropoff.get("place_id"))

        if asap:
            inst.asap = True
            inst.pickup_dt = default_tz_now() + datetime.timedelta(minutes=asap_interval())
            logging.info("ASAP set as %s" % inst.pickup_dt.strftime("%H:%M"))
        else:
            inst.pickup_dt = dateutil.parser.parse(request_data.get("pickup_dt"))

        inst.mobile = request.mobile
        inst.language_code = request.POST.get("language_code", get_language_from_request(request))
        inst.user_agent = request.META.get("HTTP_USER_AGENT")

        return inst


class Address:
    lat = 0.0
    lng = 0.0
    house_number = None
    street = ""
    city_name = ""
    country_code = ""
    name = ""
    description = ""

    def __init__(self, lat, lng, house_number=None, street=None, city_name=None, name=None, description=None, country_code=settings.DEFAULT_COUNTRY_CODE, **kwargs):
        self.lat = float(lat)
        self.lng = float(lng)

        self.house_number = house_number
        self.street = street
        self.city_name = city_name
        self.name = name
        self.description = description
        self.country_code = country_code

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
        if all([self.street, self.house_number, self.city_name]):
            return u"%s %s, %s" % (self.street, self.house_number, self.city_name)
        else:
            return self.name or ""


    def __eq__(self, other):
        return self.__hash__() == other.__hash__()

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return self.formatted_address.__hash__()

