# This Python file uses the following encoding: utf-8
import os
from django.contrib.auth.models import User
from google.appengine.api import memcache
from google.appengine.api.channel.channel import InvalidChannelClientIdError
from billing.enums import BillingStatus
from common.errors import TransactionError
from common.geocode import gmaps_geocode, Bounds, gmaps_reverse_geocode
from django.core.urlresolvers import reverse
from google.appengine.ext.deferred import deferred
from google.appengine.api.channel import channel
from billing.models import BillingTransaction
from common.decorators import force_lang
from common.models import City
from common.util import custom_render_to_response, get_uuid, base_datepicker_page, send_mail_as_noreply, is_in_hebrew
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse, HttpResponseBadRequest
from django.utils import simplejson, translation
from django.utils.translation import get_language_from_request
from django.shortcuts import render_to_response, get_object_or_404
from django.template.context import RequestContext
from common.tz_support import  default_tz_now, set_default_tz_time, default_tz_now_min, default_tz_now_max, IsraelTimeZone
import dateutil
from django.views.decorators.csrf import csrf_exempt
from djangotoolbox.http import JSONResponse
from fleet.fleet_manager import POSITION_CHANGED, cancel_ride
import ordering
from ordering.decorators import passenger_required
from ordering.enums import RideStatus
from ordering.forms import OrderForm
from ordering.models import StopType, RideComputation, RideComputationSet, OrderType, RideComputationStatus, ORDER_STATUS, Order, Passenger, SharedRide, IGNORED, REJECTED, FAILED, ERROR, TIMED_OUT, CANCELLED, Station
from pricing.views import hotspot_pricing_overview
import sharing
from sharing.forms import ConstraintsForm
from sharing.models import HotSpot
from sharing.passenger_controller import HIDDEN_FIELDS
from sharing.algo_api import submit_orders_for_ride_calculation
from datetime import  datetime, date, timedelta
from datetime import time as dt_time
import logging
import time
import settings
import re

POINT_ID_REGEXPT = re.compile("^(p\d+)_")
LANG_CODE = "he"
PICKMEAPP = "PickMeApp"

@staff_member_required
@force_lang("en")
def control_panel(request):
    admin_links = [
            {'name': 'Kpi', 'url': reverse(kpi)},
            {'name': 'Birdseye', 'url': reverse(birdseye_view)},
            {'name': 'Track rides and taxis', 'url': reverse(track_rides)},
            {'name': 'Hotspot pricing', 'url': reverse(hotspot_pricing_overview)},
            {'name': 'Sharing orders map', 'url': reverse(sharing_orders_map)},
            {'name': 'PickMeApp orders map', 'url': reverse(pickmeapp_orders_map)},
            {'name': 'Staff home', 'url': reverse(staff_home)},
            {'name': 'Google maps testing page', 'url': reverse(gmaps)},
    ]
    data_generators = [
            {'name': 'Send users data', 'url': reverse(send_users_data_csv)},
            {'name': 'Send orders data', 'url': reverse(send_orders_data_csv)},
    ]
    external_services = [
            {'name': 'Google cloud print', 'description': 'Login as printer@waybetter.com', 'url': 'http://www.google.com/cloudprint/'},
            {'name': 'invoice4U', 'url': 'https://account.invoice4u.co.il/login.aspx?ReturnUrl=/User/Default.aspx'},
            {'name': 'freefax', 'url': 'http://www.freefax.co.il/login.php'},
            {'name': 'myfax', 'url': 'https://myfax.co.il/action/faxLogs.do?listType=outbox'},
    ]

    catagories = [
            {'title': 'Admin Links', 'data': admin_links},
            {'title': 'Data Generation', 'data': data_generators},
            {'title': 'External Services', 'data': external_services},
    ]

    sys_consts = [
            {'name': 'Sharing factor (Minutes)', 'value': ordering.models.SHARING_TIME_MINUTES},
            {'name': 'Ride handling time (Minutes)', 'value': int(sharing.models.TOTAL_HANDLING_DELTA.seconds)/60},
    ]

    env_vars = [
            {'name': 'SERVER_SOFTWARE', 'value': os.environ.get('SERVER_SOFTWARE')},
            {'name': 'CURRENT_VERSION_ID', 'value': os.environ.get('CURRENT_VERSION_ID')},
    ]
    for attr in ['LOCAL', 'DEV_VERSION', 'DEV', 'DEBUG']:
        env_vars.append({'name': attr, 'value': getattr(settings, attr)})

    return render_to_response("staff_cpanel.html", locals(), context_instance=RequestContext(request))


@staff_member_required
def gmaps(request):
    return render_to_response("gmaps_testpage.html", locals(), context_instance=RequestContext(request))

def gmaps_resolve_address(request):
    address = request.GET.get("address")
    lang_code = 'iw' if is_in_hebrew(address) else 'en'
    tel_aviv_bounds = Bounds({
        "sw_lat": "32.032819",
        "sw_lon": "34.741859",
        "ne_lat": "32.132594",
        "ne_lon": "34.83284"
    })
    geocoding_results =  gmaps_geocode(address=address, lang_code=lang_code, bounds=tel_aviv_bounds)
    results = []
    for result in geocoding_results:
        results.append({
            'description': '%s (%s)' % (result['formatted_address'], ", ".join(result['types'])),
            'raw_data': simplejson.dumps(result)
        })
    return JSONResponse({'results': results})

def reverse_geocode(request):
    lat = request.GET.get("lat")
    lon = request.GET.get("lon")
    lang_code = 'iw'

    results = gmaps_reverse_geocode(lat, lon, lang_code=lang_code)
    return JSONResponse({'results': results})

@staff_member_required
def view_user_orders(request, user_id):
    user = User.objects.get(id=user_id)
    try:
        passenger = user.passenger
        orders = sorted(passenger.orders.filter(type=OrderType.SHARED, debug=False), key=lambda order: order.create_date)
        title = "View sharing order for user: %s [%s]" % (user.get_full_name(), user.email)

    except Passenger.DoesNotExist:
        title = "User is not a passenger"

    return custom_render_to_response("staff_user_orders.html", locals(), context_instance=RequestContext(request))

def calc_users_data_csv(recipient ,offset=0, csv_bytestring=u""):
    batch_size = 500
    datetime_format = "%d/%m/%y"
    link_domain = "www.waybetter.com"

    logging.info("querying users %s->%s" % (offset, offset + batch_size))
    users = User.objects.order_by("-last_login")[offset: offset + batch_size]
    for user in users:
        link = "http://%s/%s" % (link_domain , reverse(view_user_orders, args=[user.id]))
        last_login = user.last_login.strftime(datetime_format)
        date_joined = user.date_joined.strftime(datetime_format)
        full_name = user.get_full_name()
        email = user.email
        phone = ""
        billing_info = ""
        last_order_date = ""
        num_orders_mobile = ""
        num_orders_website = ""
        num_rides = ""
        total_payment = ""
        try:
            passenger = user.passenger
            phone = passenger.phone
            if hasattr(passenger, "billing_info"):
                billing_info = "yes"
            orders = sorted(passenger.orders.filter(type=OrderType.SHARED, debug=False), key=lambda order: order.create_date)

            num_orders = len(orders)
            if num_orders:
                last_order_date = orders[0].create_date.strftime(datetime_format)
                dispatched_orders = filter(lambda o: o.ride, orders)
                total_payment = sum([order.price for order in dispatched_orders])
                num_rides = len(dispatched_orders)
                num_orders_mobile = len(filter(lambda o: o.mobile, orders))
                num_orders_website = num_orders - num_orders_mobile
        except Passenger.DoesNotExist:
            pass
        except Passenger.MultipleObjectsReturned:
            pass

        user_data = [last_login, last_order_date, date_joined, full_name, email, phone, num_orders_mobile, num_orders_website, num_rides, billing_info, total_payment, link]
        csv_bytestring += u",".join([unicode(i).replace(",", "") for i in user_data])
        csv_bytestring += u"\n"

    if users:
        deferred.defer(calc_users_data_csv, recipient, offset=offset + batch_size + 1, csv_bytestring=csv_bytestring)
    else:
        logging.info("all done, sending data...")
        timestamp = date.today()
        send_mail_as_noreply(recipient, "Users data %s" % timestamp, attachments=[("users_data_%s.csv" % timestamp, csv_bytestring)])


@staff_member_required
def send_users_data_csv(request):
    recipient = ["dev@waybetter.com"]
    col_names = ["Last Seen", "Last Ordered", "Joined", "Name", "email", "Phone", "#mobile orders", "#website orders", "#rides", "billing", "total payment", "view orders"]
    deferred.defer(calc_users_data_csv, recipient, offset=0, csv_bytestring=u"%s\n" % u",".join(col_names))

    return HttpResponse("An email will be sent to %s in a couple of minutes" % recipient)

def calc_orders_data_csv(recipient, batch_size, offset=0, csv_bytestring=u"", calc_cost=False):
    link_domain = "www.waybetter.com"

    logging.info("querying computations %s->%s" % (offset, offset + batch_size))

    start_dt = set_default_tz_time(datetime(2012, 1, 1))
    end_dt = set_default_tz_time(datetime.now())
    station, station_cost_rules = None, []

    computations = RideComputation.objects.filter(create_date__gte=start_dt, create_date__lte=end_dt).order_by("create_date")[offset: offset + batch_size]
    for computation in computations:
        if computation.debug:
            continue

        rides = computation.rides.all()
        total_interval_orders = sum([ride.orders.count() for ride in rides])

        for ride in rides:
            orders = ride.orders.all()
            count_orders = len(orders)
            for order in orders:
                depart_day = order.depart_time.date().isoformat() if order.depart_time else ""
                depart_time = order.depart_time.time().strftime("%H:%M") if order.depart_time else ""
                arrive_day = order.arrive_time.date().isoformat() if order.arrive_time else ""
                arrive_time = order.arrive_time.time().strftime("%H:%M") if order.arrive_time else ""
                hotspot_type = computation.get_hotspot_type_display()

                ordering_td = (order.depart_time or order.arrive_time) - order.create_date
                ordering_td_format = str(ordering_td).split(".")[0] # trim microseconds

                passenger_name = order.passenger.full_name
                shared = "yes" if count_orders > 1 else ""
                price = order.price
                cost = 0

                if calc_cost:
                    if ride.station and ride.station != station: # store the rules in memory to reduce queries
                        station = ride.station
                        station_cost_rules = list(ride.station.fixed_prices.all())
                        logging.info("got new prices from station %s (was %s)" % (ride.station, station))
                    for rule in station_cost_rules:
                        if rule.is_active(order.from_lat, order.from_lon, order.to_lat, order.to_lon,ride.depart_time.date(), ride.depart_time.time()):
                            cost = rule.price

                link = "http://%s/%s" % (link_domain , reverse(ride_page, args=[ride.id]))

                order_data = [depart_day, depart_time, arrive_day, arrive_time, ordering_td_format, passenger_name,
                              order.from_raw, order.from_lat, order.from_lon, order.to_raw, order.to_lat, order.to_lon,
                              hotspot_type, shared, order.computation_id, total_interval_orders, price, cost, link]
                csv_bytestring += u";".join([unicode(i).replace(";", "").replace('"', '') for i in order_data])
                csv_bytestring += u"\n"

    if computations:
        deferred.defer(calc_orders_data_csv, recipient, batch_size, offset=offset + batch_size + 1, csv_bytestring=csv_bytestring, calc_cost=calc_cost)
    else:
        logging.info("all done, sending data...")
        timestamp = date.today()
        send_mail_as_noreply(recipient, "Orders data %s" % timestamp, attachments=[("orders_data_%s.csv" % timestamp, csv_bytestring)])

@staff_member_required
def send_orders_data_csv(request):
    recipient = [request.GET.get("recipient", "dev@waybetter.com")]
    batch_size = request.GET.get("batch_size")
    if not batch_size:
        batch_size = 800
    else:
        batch_size = int(batch_size)
    calc_cost = bool(request.GET.get("calc_cost"))

    col_names = ["depart day", "depart time", "arrive day", "arrive time", "ordered before pickup", "passenger",
                 "from", "from lat", "from lon", "to", "to lat", "to lon", "hotspot_type",
                 "sharing?", "interval id", "#interval orders", "price", "cost", "ride map"]

    deferred.defer(calc_orders_data_csv, recipient, batch_size, offset=0, csv_bytestring=u"%s\n" % u";".join(col_names), calc_cost=calc_cost)
    return HttpResponse("An email will be sent to %s in a couple of minutes" % ",".join(recipient))


@staff_member_required
def count_query(request):
    # e.g. /count_query?model=SharedRide&q={status:1}
    from django.db.models.loading import get_model
    def _decode_dict(data):
        rv = {}
        for key, value in data.iteritems():
            if isinstance(key, unicode):
               key = key.encode('utf-8')
            if isinstance(value, unicode):
               value = value.encode('utf-8')
            elif isinstance(value, list):
               value = _decode_list(value)
            elif isinstance(value, dict):
               value = _decode_dict(value)
            rv[key] = value
        return rv

    count = "?"
    m = request.GET.get("model")
    q = request.GET.get("q", u"{}")
    d = simplejson.loads(q.encode("utf-8"), object_hook=_decode_dict)
    if m:
        for app in settings.INSTALLED_APPS:
            model = get_model(app, m)
            if model:
                qs = model.objects.filter(**d)
                count = qs.count()
                logging.info("model = %s" % model)

    return HttpResponse("Count = %s" % count)


@staff_member_required
def passenger_csv(request):
    p_count = 0
    o_count = 0
    for p in Passenger.objects.all():
        p_count += 1
        o_count += p.orders.filter(debug=False).count()


@staff_member_required
def sharing_orders_map(request):
    return order_map(request, "sharing")

@staff_member_required
def pickmeapp_orders_map(request):
    return order_map(request, PICKMEAPP, msgs=["# Orders = 4405", "Avg. Freq = 1 order / 4.5 days"])

def order_map(request, type, msgs=None):
    pickmeapp = PICKMEAPP

#    total_pickmeapp = Order.objects.filter(type=OrderType.PICKMEAPP, debug=False).count()
#    total_sharing = Order.objects.filter(type=OrderType.SHARED, debug=False).count()
#    status_options = ORDER_STATUS
    return render_to_response("orders_map.html", RequestContext(request, locals()))

def get_orders_map_data(request):
    offset = int(request.GET.get("offset", 0))
    batch_size = int(request.GET.get("batch_size", 500))
    request_type = request.GET.get("type", PICKMEAPP)
    status = None
#    try:
#        status = int(request.GET.get("status"))
#    except ValueError, e:
#        pass

    count_only = request.GET.get("count_only", False)
    if count_only: count_only = simplejson.loads(count_only)

    if request_type == PICKMEAPP:
        orders = Order.objects.filter(type=OrderType.PICKMEAPP, debug=False)
    else:
        orders = Order.objects.filter(type=OrderType.SHARED, debug=False)

    if not status is None: orders = orders.filter(status=status)

    if count_only:
        return JSONResponse(orders.count())
    else:
        orders = orders[offset:offset + batch_size]

    points = []
    for o in orders:
        if o.from_lat and o.from_lon:
            points.append([o.from_lat, o.from_lon, o.passenger_id])

    return JSONResponse(points)

@staff_member_required
@force_lang("en")
def kpi(request):
    na = "N/A"
    init_start_date = default_tz_now_min() - timedelta(days=1)
    init_end_date = default_tz_now_max()
    channel_id = get_uuid()
    token = channel.create_channel(channel_id)

    from analytics.kpi import calc_kpi_data
    return base_datepicker_page(request, calc_kpi_data, 'kpi.html', locals(), init_start_date, init_end_date, async=True)

@staff_member_required
def kpi_csv(request):
    #    r = int(request.GET.get("range", 4))
#    deferred.defer(kpi.calc_kpi2, r)

#    deferred.defer(kpi.calc_kpi3)
#    deferred.defer(kpi.calc_ny_sharing)
#    deferred.defer(kpi.calc_order_timing)
#    deferred.defer(kpi.calc_station_rating)
#    deferred.defer(kpi.calc_passenger_ride_freq)
#    deferred.defer(kpi.calc_passenger_rides)
#    deferred.defer(kpi.calc_order_per_day_pickmeapp)
#    deferred.defer(kpi.calc_pickmeapp_passenger_count)
    return HttpResponse("OK")

@staff_member_required
def birdseye_view(request):
    na = "N/A"
    init_start_date = default_tz_now_min()
    init_end_date = default_tz_now_max() + timedelta(days=7)
    order_status_labels = [label for (key, label) in ORDER_STATUS]

    def srz_o(o):
        _from, _to = o.from_raw, o.to_raw
        passenger_details = None
        if o.passenger:
            passenger_details = [o.passenger.full_name, o.passenger.phone]
            if o.passenger.user:
                passenger_details.append(o.passenger.user.email)
        if o.hotspot:
            if o.hotspot_type == StopType.PICKUP: _from = o.hotspot.name
            if o.hotspot_type == StopType.DROPOFF: _to = o.hotspot.name

        booked = ""
        hh, mm = divmod((o.depart_time - o.create_date).seconds / 60, 60)
        if hh: booked += "%sh" % hh
        if mm: booked += " %smin" % mm

        return {'id': o.id,
                'date': o.depart_time.strftime("%d/%m/%y"),
                'depart': "%s %s" % (_from, o.depart_time.strftime("%H:%M")),
                'arrive': "%s %s" % (_to, o.arrive_time.strftime("%H:%M")),
                'booked': booked,
                'passenger': " ".join(passenger_details) if passenger_details else na,
                'type': OrderType.get_name(o.type),
                'status': o.get_status_label(),
                'price': o.price,
                'debug': 'Yes' if o.debug else 'No'
        }

    def srz_r(r):
        return {'id': r.id,
                'depart_time': r.depart_time.strftime("%H:%M"),
                'orders': [srz_o(o) for o in r.orders.all()]
        }

    def f(start_date, end_date):
        orders = Order.objects.filter(depart_time__gte=start_date, depart_time__lte=end_date)
        private_orders = filter(lambda o: o.type == OrderType.PRIVATE, orders)
        private_orders_data = [srz_o(o) for o in sorted(private_orders, key=lambda o: o.depart_time, reverse=True)]

        computations = RideComputation.objects.filter(hotspot_datetime__gte=start_date, hotspot_datetime__lte=end_date)
        computations_data = []
        for c in sorted(computations, key=lambda c: c.hotspot_datetime, reverse=True):
            time = c.hotspot_datetime
            status = RideComputationStatus.get_name(c.status)
            if c.status == RideComputationStatus.PENDING and c.submit_datetime:
                status = "%s@%s" % (status, c.submit_datetime.strftime("%H:%M"))
            c_data = {'id': c.id,
                      'status': status,
                      'time': time.strftime("%d/%m/%y, %H:%M"),
                      'dir': 'Hotspot->' if c.hotspot_type == StopType.PICKUP else '->Hotspot' if c.hotspot_type == StopType.DROPOFF else na,
                      }
            if c.rides.count():
                non_ride_orders = [o for o in filter(lambda o: not o.ride, c.orders.all())]
                c_data['rides'] = [srz_r(r) for r in c.rides.all()]
                c_data['orders'] = [srz_o(o) for o in non_ride_orders]
            else:
                c_data['orders'] = [srz_o(o) for o in c.orders.all()]
            computations_data.append(c_data)

        return {'private_orders': private_orders_data, 'computations': computations_data}

    return base_datepicker_page(request, f, 'birdseye_view.html', locals(), init_start_date, init_end_date)


@staff_member_required
def staff_home(request):
    page_specific_class = "wb_home staff_home"
    hidden_fields = HIDDEN_FIELDS

    order_types = simplejson.dumps({'private': OrderType.PRIVATE,
                                    'shared': OrderType.SHARED})

    country_code = settings.DEFAULT_COUNTRY_CODE

    cities = [{'id': city.id, 'name': city.name} for city in City.objects.filter(name="תל אביב יפו")]

    is_debug = True

    return custom_render_to_response('wb_home.html', locals(), context_instance=RequestContext(request))


@staff_member_required
@passenger_required
def hotspot_ordering_page(request, passenger, is_textinput):
    translation.activate(LANG_CODE)

    if request.method == 'POST':
        response = ''
        hotspot_type_raw = request.POST.get("hotspot_type", None)

        if hotspot_type_raw in ["pickup", "dropoff"]:
            hotspot_type, point_type = ("from", "to") if hotspot_type_raw == "pickup" else ("to", "from")
            data = request.POST.copy()
            data['passenger'] = passenger
            orders = create_orders_from_hotspot(data, hotspot_type, point_type, is_textinput)

            if orders:
                params = {}
                if float(request.POST.get("time_const_frac") or 0):
                    params["toleration_factor"] = request.POST["time_const_frac"]
                if int(request.POST.get("time_const_min") or 0):
                    params["toleration_factor_minutes"] = request.POST["time_const_min"]
                name = request.POST.get("computation_set_name")
                key = submit_test_computation(orders, hotspot_type_raw, params=params, computation_set_name=name)
                response = u"Orders submitted for calculation: %s" % key
            else:
                response = "Hotspot data corrupt: no orders created"
        else:
            response = "Hotspot type invalid"

        return HttpResponse(response)

    else: # GET
        is_popup = True
        page_specific_class = "hotspot_page"
        hidden_fields = HIDDEN_FIELDS

        hotspots = [{'name': hotspot.name, 'id': hotspot.id, 'lon': hotspot.lon, 'lat': hotspot.lat}
        for hotspot in HotSpot.objects.all()]

        telmap_user = settings.TELMAP_API_USER
        telmap_password = settings.TELMAP_API_PASSWORD
        telmap_languages = 'he' if str(get_language_from_request(request)) == 'he' else 'en'
        country_code = settings.DEFAULT_COUNTRY_CODE

        constraints_form = ConstraintsForm()

        if is_textinput:
            page_specific_class = "%s textinput" % page_specific_class
            hotspot_times = sorted(map(lambda i: "%d:00" % i, range(0, 24)) +
                                   map(lambda i: "%d:30" % i, range(0, 24)),
                                   key=lambda v: int(v.split(":")[0])) # sorry about that :)
            return render_to_response('hotspot_ordering_page_textinput.html', locals(),
                                      context_instance=RequestContext(request))
        else:
            return render_to_response('hotspot_ordering_page.html', locals(), context_instance=RequestContext(request))


@staff_member_required
def ride_computation_stat(request, computation_set_id):
    computation_set = get_object_or_404(RideComputationSet, id=computation_set_id)
    orders = computation_set.orders

    if request.method == 'POST':
        params = {}
        if float(request.POST.get("time_const_frac") or 0):
            params["toleration_factor"] = request.POST["time_const_frac"]
        if int(request.POST.get("time_const_min") or 0):
            params["toleration_factor_minutes"] = request.POST["time_const_min"]

        key = submit_test_computation(orders, "pickup", params=params, computation_set_id=computation_set.id)
        return JSONResponse({'content': u"Orders submitted for calculation: %s" % key})

    else:
        is_popup = True
        telmap_user = settings.TELMAP_API_USER
        telmap_password = settings.TELMAP_API_PASSWORD
        telmap_languages = 'he'
        pickup = StopType.PICKUP
        dropoff = StopType.DROPOFF
        constrains_form = ConstraintsForm()

        points = set([order.pickup_point for order in orders] + [order.dropoff_point for order in orders])
        points = simplejson.dumps([{'id': p.id, 'lat': p.lat, 'lon': p.lon, 'address': p.address, 'type': p.type}
        for p in sorted(points, key=lambda p: p.stop_time)])

        computations = [{'id': c.id,
                         'stat': simplejson.loads(c.statistics),
                         'toleration_factor': c.toleration_factor,
                         'toleration_factor_minutes': c.toleration_factor_minutes} for c in
                                                                                   computation_set.members.filter(
                                                                                       status=RideComputationStatus.COMPLETED)]

        return render_to_response('ride_computation_stat.html', locals(), context_instance=RequestContext(request))


def create_orders_from_hotspot(data, hotspot_type, point_type, is_textinput):
    fields = ["raw"] + HIDDEN_FIELDS

    if is_textinput:
        hotspot_data = {}
        for f in fields:
            hotspot_data["%s_%s" % (hotspot_type, f)] = data.get("hotspot_%s" % f, None)
        hotspot_datetime = datetime.combine(default_tz_now().date(),
                                            datetime.strptime(data.get("hotspot_time"), "%H:%M").time())
        hotspot_datetime = set_default_tz_time(hotspot_datetime)

    else:
        hotspot = HotSpot.by_id(data.get("hotspot_id"))
        hotspot_data = hotspot.serialize_for_order(hotspot_type)
        hotspot_time = datetime.strptime(data.get("hotspot_time"), "%H:%M").time()
        hotspot_date = date(*time.strptime(data.get("hotspot_date"), '%d/%m/%Y')[:3])
        hotspot_datetime = set_default_tz_time(datetime.combine(hotspot_date, hotspot_time))

    orders = []
    if all(hotspot_data.values()) and hotspot_datetime:
        p_names = []
        for f in data.keys():
            p_name = re.search(POINT_ID_REGEXPT, f)
            if p_name and p_name.groups()[0] not in p_names:
                p_names.append(p_name.groups()[0])

        points = []
        for p_name in p_names:
            p_data = {}
            for f in fields:
                p_data["%s_%s" % (point_type, f)] = data.get("%s_%s" % (p_name, f), None)

            if all(p_data.values()):
                points.append(p_data)

        for p_data in points:
            form_data = p_data.copy()
            form_data.update(hotspot_data)
            form = OrderForm(form_data)
            if form.is_valid():
                order = form.save(commit=False)
                price = None
                if hotspot_type == "from":
                    order.depart_time = hotspot_datetime
                    price = hotspot.get_sharing_price(order.to_lat, order.to_lon, hotspot_datetime.date(),
                                                      hotspot_datetime.time())
                else:
                    order.arrive_time = hotspot_datetime
                    order.depart_time = hotspot_datetime
                    price = hotspot.get_sharing_price(order.from_lat, order.from_lon, hotspot_datetime.date(),
                                                      hotspot_datetime.time())

                passenger = data['passenger']
                order.passenger = passenger
                order.confining_station = passenger.default_sharing_station
                order.language_code = LANG_CODE
                order.save()

                if price and hasattr(passenger, "billing_info"):
                    billing_trx = BillingTransaction(order=order, amount=price, debug=order.debug)
                    billing_trx.save()
                    billing_trx.commit()

                orders.append(order)

    return orders


def submit_test_computation(orders, hotspot_type_raw, params, computation_set_name=None, computation_set_id=None):
    key = "test_%s" % str(default_tz_now())
    params.update({'debug': True})
    algo_key = submit_orders_for_ride_calculation(orders, key=key, params=params)

    if algo_key:
        computation = RideComputation(algo_key=algo_key, debug=True)
        computation.change_status(new_status=RideComputationStatus.SUBMITTED)
        computation.toleration_factor = params.get('toleration_factor')
        computation.toleration_factor_minutes = params.get('toleration_factor_minutes')
        order = orders[0]
        if hotspot_type_raw == "pickup":
            computation.hotspot_type = StopType.PICKUP
            computation.hotspot_datetime = order.depart_time
        else:
            computation.hotspot_type = StopType.DROPOFF
            computation.hotspot_datetime = order.arrive_time

        if computation_set_id: # add to existing set
            computation_set = RideComputationSet.by_id(computation_set_id)
            computation.set = computation_set
        elif computation_set_name: # create new set
            computation_set = RideComputationSet(name=computation_set_name)
            computation_set.save()
            computation.set = computation_set

        computation.save()

        for order in orders:
            order.computation = computation
            order.save()

    return algo_key

@force_lang("en")
@staff_member_required
def eagle_eye(request):
    lib_ng = True
    stations = simplejson.dumps([{"name": s.name, "id": s.id} for s in Station.objects.all()]);
#    status_values = dict([(label.encode('utf-8').upper(), label.encode('utf-8').upper()) for key, label in ORDER_STATUS])
    return render_to_response("eagle_eye.html", locals(), context_instance=RequestContext(request))

@force_lang("en")
def eagle_eye_data(request):
    start_date = dateutil.parser.parse(request.GET.get("start_date")).astimezone(IsraelTimeZone())
    end_date = dateutil.parser.parse(request.GET.get("end_date")).astimezone(IsraelTimeZone())

    start_date = datetime.combine(start_date, dt_time.min)
    end_date = datetime.combine(end_date, dt_time.max)

    logging.info("start_date = %s, end_date = %s" % (start_date, end_date))

    rides = SharedRide.objects.filter(depart_time__gte=start_date, depart_time__lte=end_date).order_by("-depart_time")
    incomplete_orders = Order.objects.filter(depart_time__gte=start_date, depart_time__lte=end_date)
    incomplete_orders = filter(lambda o: o.status in [IGNORED, REJECTED, FAILED, ERROR, TIMED_OUT, CANCELLED], incomplete_orders)

    logging.info("incomplete_orders = %s" % incomplete_orders)

    result = {
        'rides': [],
        'incomplete_orders': []
    }

    for ride in rides:
        result['rides'].append(ride.serialize_for_eagle_eye())

    for order in incomplete_orders:
        result['incomplete_orders'].append(order.serialize_for_eagle_eye())

    return JSONResponse(result)

@csrf_exempt
@staff_member_required
@force_lang("en")
def manual_assign_ride(request):
    ride_id = request.POST.get("ride_id")
    station_id = request.POST.get("station_id")
    ride = SharedRide.by_id(ride_id)
    station = Station.by_id(station_id)
    if station and ride.station != station:
        cancel_ride(ride)
        ride.station = station
        ride.change_status(new_status=RideStatus.ASSIGNED)

    return JSONResponse({'ride': ride.serialize_for_eagle_eye()})

@staff_member_required
@force_lang("en")
def ride_page(request, ride_id):
    lib_ng = True
    lib_map = True
    position_changed = POSITION_CHANGED

    return render_to_response("ride_page.html", locals(), context_instance=RequestContext(request))

@staff_member_required
@force_lang("en")
def cancel_billing(request, order_id):
    order = Order.by_id(order_id)
    for bt in order.billing_transactions.all():
        if bt.status not in [BillingStatus.CANCELLED, BillingStatus.CHARGED]:
            try:
                bt.disable()
            except TransactionError, e:
                return HttpResponseBadRequest("Transaction[%s] could not be cancelled: %s" % (bt.id, e))

    order.change_status(new_status=CANCELLED)
    order = order.fresh_copy()
    return JSONResponse({
        "success": True,
        "order": order.serialize_for_eagle_eye()
    })

TRACK_RIDES_CHANNEL_MEMCACHE_KEY = "track_rides_channel_memcache_key"
#@staff_member_required
@force_lang("en")
def track_rides(request):
    lib_channel = True
    lib_map = True

    channel_id = get_uuid()
    cids = memcache.get(TRACK_RIDES_CHANNEL_MEMCACHE_KEY) or []
    cids.append(channel_id)
    memcache.set(TRACK_RIDES_CHANNEL_MEMCACHE_KEY, cids)

    token = channel.create_channel(channel_id)

#    ongoing_rides = fleet_manager.get_ongoing_rides()
#    fmr = FleetManagerRide(1234, 5, 123, 32.1, 34.1, datetime.now(), "raw_status")
#    ongoing_rides = [fmr]
    return render_to_response("staff_track_rides.html", locals(), context_instance=RequestContext(request))

def _log_fleet_update(json):
    logging.info("fleet update: %s" % json)
    cids = memcache.get(TRACK_RIDES_CHANNEL_MEMCACHE_KEY) or []
    live_cids = []

    for cid in cids:
        try:
            channel.send_message(cid, json)
            live_cids.append(cid)
        except InvalidChannelClientIdError, e:
            pass

    memcache.set(TRACK_RIDES_CHANNEL_MEMCACHE_KEY, live_cids)