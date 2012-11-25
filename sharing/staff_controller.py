# This Python file uses the following encoding: utf-8
import os
from django.contrib.auth.models import User
from google.appengine.api import memcache
from google.appengine.api.channel.channel import InvalidChannelClientIdError
from billing.enums import BillingStatus
from common.errors import TransactionError
from django.core.urlresolvers import reverse
from google.appengine.ext.deferred import deferred
from google.appengine.api.channel import channel
from common.decorators import force_lang
from common.util import custom_render_to_response, get_uuid, base_datepicker_page, send_mail_as_noreply
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse, HttpResponseBadRequest
from django.utils import simplejson
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from common.tz_support import   set_default_tz_time, default_tz_now_min, default_tz_now_max, IsraelTimeZone
import dateutil
from django.views.decorators.csrf import csrf_exempt
from djangotoolbox.http import JSONResponse
from fleet import fleet_manager
import ordering
from ordering.enums import RideStatus
from ordering.models import OrderType, Order, Passenger, SharedRide, IGNORED, REJECTED, FAILED, ERROR, TIMED_OUT, CANCELLED, Station
from datetime import  datetime, date, timedelta
from datetime import time as dt_time
import logging
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
            {'name': 'EagleEye', 'url': reverse(eagle_eye)},
            {'name': 'Track rides and taxis', 'url': reverse(track_rides)},
            {'name': 'Hotspot pricing', 'url': reverse(hotspot_pricing_overview)},
            {'name': 'Sharing orders map', 'url': reverse(sharing_orders_map)},
            {'name': 'PickMeApp orders map', 'url': reverse(pickmeapp_orders_map)},
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
            {'name': 'Ride handling time (Minutes)', 'value': 0}, #TODO_WB: fix this value
    ]

    env_vars = [
            {'name': 'SERVER_SOFTWARE', 'value': os.environ.get('SERVER_SOFTWARE')},
            {'name': 'CURRENT_VERSION_ID', 'value': os.environ.get('CURRENT_VERSION_ID')},
    ]
    for attr in ['LOCAL', 'DEV_VERSION', 'DEV', 'DEBUG']:
        env_vars.append({'name': attr, 'value': getattr(settings, attr)})

    return render_to_response("staff_cpanel.html", locals(), context_instance=RequestContext(request))

@staff_member_required
def view_passenger_orders(request, passenger_id):
    passenger = Passenger.by_id(passenger_id)
    user = passenger.user
    orders = sorted(passenger.orders.filter(type=OrderType.SHARED, debug=False), key=lambda order: order.create_date)
    title = "View sharing order for passenger: %s [%s]" % (user.get_full_name(), user.email)

    return custom_render_to_response("staff_user_orders.html", locals(), context_instance=RequestContext(request))

def calc_users_data_csv(recipient ,offset=0, csv_bytestring=u""):
    batch_size = 500
    datetime_format = "%d/%m/%y"
    link_domain = "www.waybetter.com"

    logging.info("querying users %s->%s" % (offset, offset + batch_size))
    users = User.objects.order_by("-last_login")[offset: offset + batch_size]
    for user in users:
        link = ""
        last_login = user.last_login.strftime(datetime_format)
        date_joined = user.date_joined.strftime(datetime_format)
        first_name = user.first_name
        last_name = user.last_name
        email = user.email
        phone = ""
        billing_info = ""
        first_order_date = ""
        last_order_date = ""
        num_orders_mobile = ""
        num_orders_website = ""
        num_rides = ""
        total_payment = ""
        try:
            passenger = user.passenger
            link = "http://%s/%s" % (link_domain , reverse(view_passenger_orders, args=[passenger.id]))
            phone = passenger.phone
            if hasattr(passenger, "billing_info"):
                billing_info = "yes"
            orders = sorted(passenger.orders.filter(type=OrderType.SHARED, debug=False), key=lambda order: order.create_date)

            num_orders = len(orders)
            if num_orders:
                first_order_date = orders[0].create_date.strftime(datetime_format)
                last_order_date = orders[-1].create_date.strftime(datetime_format)
                dispatched_orders = filter(lambda o: o.ride, orders)
                total_payment = sum([order.get_billing_amount() for order in dispatched_orders])
                num_rides = len(dispatched_orders)
                num_orders_mobile = len(filter(lambda o: o.mobile, orders))
                num_orders_website = num_orders - num_orders_mobile
        except Passenger.DoesNotExist:
            pass
        except Passenger.MultipleObjectsReturned:
            pass

        user_data = [last_login, first_order_date, last_order_date, date_joined, first_name, last_name, email, phone, num_orders_mobile, num_orders_website, num_rides, billing_info, total_payment, link]
        csv_bytestring += u",".join([unicode(i).replace(",", "") for i in user_data])
        csv_bytestring += u"\n"

    if users:
        deferred.defer(calc_users_data_csv, recipient, offset=offset + batch_size + 1, csv_bytestring=csv_bytestring)
    else:
        logging.info("all done, sending data...")
        timestamp = date.today()
        logging.info(csv_bytestring)
        send_mail_as_noreply(recipient, "Users data %s" % timestamp, attachments=[("users_data_%s.csv" % timestamp, csv_bytestring)])

@staff_member_required
def send_users_data_csv(request):
    recipient = ["dev@waybetter.com"]
    col_names = ["Last Login", "First Ordered", "Last Ordered", "Joined", "First Name", "Last Name", "email", "Phone", "#mobile orders", "#website orders", "#rides", "billing", "total payment", "view orders"]
    deferred.defer(calc_users_data_csv, recipient, offset=0, csv_bytestring=u"%s\n" % u",".join(col_names))

    return HttpResponse("An email will be sent to %s in a couple of minutes" % recipient)

def calc_orders_data_csv(recipient, batch_size, offset=0, csv_bytestring=u"", calc_cost=False):
    link_domain = "www.waybetter.com"

    logging.info("querying computations %s->%s" % (offset, offset + batch_size))

    start_dt = set_default_tz_time(datetime(2012, 1, 1))
    end_dt = set_default_tz_time(datetime.now())
    station, station_cost_rules = None, []

    computations = [] #TODO_WB: no computations any more... fix if needed
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
                price = order.get_billing_amount()
                cost = 0

                if calc_cost:
                    if ride.station and ride.station != station: # store the rules in memory to reduce queries
                        station = ride.station
                        station_cost_rules = list(ride.station.fixed_prices.all())
                        logging.info("got new prices from station %s (was %s)" % (ride.station, station))
                    for rule in station_cost_rules:
                        if rule.is_active(order.from_lat, order.from_lon, order.to_lat, order.to_lon, ride.depart_time):
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

@force_lang("en")
@staff_member_required
def eagle_eye(request):
    lib_ng = True
    stations = []
    for station in Station.objects.all():
        try:
            sharing_ws = station.work_stations.filter(accept_shared_rides=True)[0]
        except Exception:
            sharing_ws = None

        stations.append({"name": station.name, "id": station.id, "online_status": sharing_ws.is_online if sharing_ws else False})

    stations = simplejson.dumps(stations)
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
    from sharing.station_controller import update_data
    from sharing.sharing_dispatcher import assign_ride

    ride_id = request.POST.get("ride_id")
    station_id = request.POST.get("station_id")
    ride = SharedRide.by_id(ride_id)
    station = Station.by_id(station_id)
    if station and ride.station != station:
        fleet_manager.cancel_ride(ride)
        old_station = ride.station

        assign_ride(ride, station)

        if old_station:
            update_data(old_station)

    return JSONResponse({'ride': ride.serialize_for_eagle_eye()})

@csrf_exempt
@staff_member_required
@force_lang("en")
def resend_to_fleet_manager(request, ride_id):
    resend_result = False

    ride = SharedRide.by_id(ride_id)
    cancel_result = fleet_manager.cancel_ride(ride)
    if cancel_result:
        resend_result = fleet_manager.create_ride(ride)

    return JSONResponse({'result': resend_result})

@csrf_exempt
@staff_member_required
@force_lang("en")
def accept_ride(request, ride_id):
    ride = SharedRide.by_id(ride_id)
    ride.change_status(new_status=RideStatus.ACCEPTED)

    return JSONResponse({'ride': ride.serialize_for_eagle_eye()})

@staff_member_required
@force_lang("en")
def ride_page(request, ride_id):
    lib_ng = True
    lib_map = True
    position_changed = fleet_manager.POSITION_CHANGED

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

    return JSONResponse({ "success": True })

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