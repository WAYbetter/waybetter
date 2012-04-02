# This Python file uses the following encoding: utf-8
from django.contrib.auth.models import User
from common.geocode import gmaps_geocode, Bounds, gmaps_reverse_geocode
from django.core.urlresolvers import reverse
from google.appengine.ext.deferred import deferred
from common.signals import async_computation_failed_signal, async_computation_completed_signal
from google.appengine.api.channel import channel
from billing.enums import BillingStatus
from billing.models import BillingTransaction, BillingInfo
from common.decorators import force_lang
from common.models import City
from common.util import custom_render_to_response, get_uuid, base_datepicker_page, send_mail_as_noreply, is_in_hebrew
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.utils import simplejson, translation
from django.utils.translation import get_language_from_request
from django.shortcuts import render_to_response, get_object_or_404
from django.template.context import RequestContext
from common.tz_support import  default_tz_now, set_default_tz_time, default_tz_now_min, default_tz_now_max
from djangotoolbox.http import JSONResponse
from ordering.decorators import passenger_required
from ordering.forms import OrderForm
from ordering.models import StopType, RideComputation, RideComputationSet, OrderType, RideComputationStatus, ORDER_STATUS, Order, CHARGED, ACCEPTED, APPROVED, REJECTED, TIMED_OUT, FAILED, Passenger, SharedRide
from sharing.forms import ConstraintsForm
from sharing.models import HotSpot
from sharing.passenger_controller import HIDDEN_FIELDS
from sharing.station_controller import show_ride
from sharing.algo_api import submit_orders_for_ride_calculation
from datetime import  datetime, date, timedelta
import logging
import time
import settings
import re

POINT_ID_REGEXPT = re.compile("^(p\d+)_")
LANG_CODE = "he"

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
    recipient = ["amir@waybetter.com", "shay@waybetter.com"]
    col_names = ["Last Seen", "Last Ordered", "Joined", "Name", "email", "Phone", "#mobile orders", "#website orders", "#rides", "billing", "total payment", "view orders"]
    deferred.defer(calc_users_data_csv, recipient, offset=0, csv_bytestring=u"%s\n" % u",".join(col_names))

    return HttpResponse("An email will be sent to %s in a couple of minutes" % recipient)

def calc_orders_data_csv(recipient ,offset=0, csv_bytestring=u""):
    batch_size = 1000
    link_domain = "www.waybetter.com"

    logging.info("querying computations %s->%s" % (offset, offset + batch_size))

    sharing_launched = set_default_tz_time(datetime(2011, 10, 1, 0, 0, 0))

    computations = RideComputation.objects.filter(create_date__gte=sharing_launched)[offset: offset + batch_size]
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

                ordering_td = (order.depart_time or order.arrive_time) - order.create_date
                ordering_td_format = str(ordering_td).split(".")[0] # trim microseconds

                passenger_name = order.passenger.full_name
                shared = "yes" if count_orders > 1 else ""
                link = "http://%s/%s" % (link_domain , reverse(show_ride, args=[ride.id]))

                order_data = [depart_day, depart_time, arrive_day, arrive_time, ordering_td_format, passenger_name,
                              order.from_raw, order.from_lat, order.from_lon, order.to_raw, order.to_lat, order.to_lon,
                              shared, order.computation_id, total_interval_orders, link]
                csv_bytestring += u",".join([unicode(i).replace(",", "") for i in order_data])
                csv_bytestring += u"\n"

    if computations:
        deferred.defer(calc_orders_data_csv, recipient, offset=offset + batch_size + 1, csv_bytestring=csv_bytestring)
    else:
        logging.info("all done, sending data...")
        timestamp = date.today()
        send_mail_as_noreply(recipient, "Orders data %s" % timestamp, attachments=[("orders_data_%s.csv" % timestamp, csv_bytestring)])

@staff_member_required
def send_orders_data_csv(request):
    recipient = ["amir@waybetter.com"]
    col_names = ["depart day", "depart time", "arrive day", "arrive time", "ordered before pickup", "passenger",
                 "from", "from lat", "from lon", "to", "to lat", "to lon",
                 "sharing?", "interval id", "#interval orders", "ride map"]
    deferred.defer(calc_orders_data_csv, recipient, offset=0, csv_bytestring=u"%s\n" % u",".join(col_names))

    return HttpResponse("An email will be sent to %s in a couple of minutes" % ",".join(recipient))

@staff_member_required
@force_lang("en")
def kpi(request):
    na = "N/A"
    init_start_date = default_tz_now_min() - timedelta(days=1)
    init_end_date = default_tz_now_max()
    channel_id = get_uuid()
    token = channel.create_channel(channel_id)

    return base_datepicker_page(request, calc_kpi_data, 'kpi.html', locals(), init_start_date, init_end_date,
                                async=True)


def calc_kpi_data(start_date, end_date, channel_id, token):
    def format_number(value, places=2, curr='', sep=',', dp='.',
                      pos='', neg='-', trailneg=''):
        """Convert Decimal to a money formatted string.

        places:  required number of places after the decimal point
        curr:    optional currency symbol before the sign (may be blank)
        sep:     optional grouping separator (comma, period, space, or blank)
        dp:      decimal point indicator (comma or period)
                 only specify as blank when places is zero
        pos:     optional sign for positive numbers: '+', space or blank
        neg:     optional sign for negative numbers: '-', '(', space or blank
        trailneg:optional trailing minus indicator:  '-', ')', space or blank

        >>> d = Decimal('-1234567.8901')
        >>> moneyfmt(d, curr='$')
        '-$1,234,567.89'
        >>> moneyfmt(d, places=0, sep='.', dp='', neg='', trailneg='-')
        '1.234.568-'
        >>> moneyfmt(d, curr='$', neg='(', trailneg=')')
        '($1,234,567.89)'
        >>> moneyfmt(Decimal(123456789), sep=' ')
        '123 456 789.00'
        >>> moneyfmt(Decimal('-0.02'), neg='<', trailneg='>')
        '<0.02>'

        """
        from decimal import Decimal

        value = Decimal(value)
        q = Decimal(10) ** -places      # 2 places --> '0.01'
        sign, digits, exp = value.quantize(q).as_tuple()
        result = []
        digits = map(str, digits)
        build, next = result.append, digits.pop
        if sign:
            build(trailneg)
        for i in range(places):
            build(next() if digits else '0')
        build(dp)
        if not digits:
            build('0')
        i = 0
        while digits:
            build(next())
            i += 1
            if i == 3 and digits:
                i = 0
                build(sep)
        build(curr)
        build(neg if sign else pos)
        return ''.join(reversed(result))

    def f():
        all_orders = list(Order.objects.filter(create_date__gte=start_date, create_date__lte=end_date))
        all_orders = filter(
            lambda o: not o.debug and o.status in [APPROVED, CHARGED, ACCEPTED, REJECTED, TIMED_OUT, FAILED],
            all_orders)
        new_passengers = Passenger.objects.filter(create_date__gte=start_date, create_date__lte=end_date).count()
        new_billing_info = BillingInfo.objects.filter(create_date__gte=start_date, create_date__lte=end_date).count()
        shared_rides = filter(lambda sr: not sr.debug,
                              SharedRide.objects.filter(create_date__gte=start_date, create_date__lte=end_date))
        shared_rides_with_sharing = filter(lambda sr: sr.stops > 1, shared_rides)
        logging.info("shared_rides (%d)" % (len(shared_rides)))
        logging.info("shared_rides_with_sharing (%d)" % (len(shared_rides_with_sharing)))

        all_trx = filter(lambda bt: not bt.debug,
                         BillingTransaction.objects.filter(status=BillingStatus.CHARGED, charge_date__gte=start_date,
                                                           charge_date__lte=end_date))

        pickmeapp_orders = filter(lambda o: not bool(o.price), all_orders)
        sharing_orders = filter(lambda o: bool(o.price), all_orders)
        accepted_orders = filter(lambda o: o.status == ACCEPTED, pickmeapp_orders)
        pickmeapp_site = filter(lambda o: not o.mobile, pickmeapp_orders)
        pickmeapp_mobile = filter(lambda o: o.mobile, pickmeapp_orders)
        pickmeapp_native = filter(lambda o: o.user_agent.startswith("PickMeApp"), pickmeapp_orders)

        sharing_site = filter(lambda o: not o.mobile, sharing_orders)
        sharing_mobile = filter(lambda o: o.mobile, sharing_orders)
        sharing_native = filter(lambda o: o.user_agent.startswith("WAYbetter"), sharing_orders)

        data = {
            "rides_booked": len(all_orders),
            "sharging_rides": len(sharing_orders),
            "sharing_site_rides": len(sharing_site),
            "sharing_mobile_rides": len(sharing_mobile),
            "sharing_native_rides": len(sharing_native),
            "sharing_site_rides_percent": round(float(len(sharing_site)) / len(sharing_orders) * 100,
                                                2) if sharing_orders else "NA",
            "sharing_mobile_rides_percent": round(float(len(sharing_mobile)) / len(sharing_orders) * 100,
                                                  2) if sharing_orders else "NA",
            "sharing_native_rides_percent": round(float(len(sharing_native)) / len(sharing_orders) * 100,
                                                  2) if sharing_orders else "NA",
            "pickmeapp_rides": len(pickmeapp_orders),
            "accepted_pickmeapp_rides": round(float(len(accepted_orders)) / len(pickmeapp_orders) * 100,
                                              2) if pickmeapp_orders else "NA",
            "pickmeapp_site_rides": len(pickmeapp_site),
            "pickmeapp_mobile_rides": len(pickmeapp_mobile),
            "pickmeapp_native_rides": len(pickmeapp_native),
            "pickmeapp_site_rides_percent": round(float(len(pickmeapp_site)) / len(pickmeapp_orders) * 100,
                                                  2) if pickmeapp_orders else "NA",
            "pickmeapp_mobile_rides_percent": round(float(len(pickmeapp_mobile)) / len(pickmeapp_orders) * 100,
                                                    2) if pickmeapp_orders else "NA",
            "pickmeapp_native_rides_percent": round(float(len(pickmeapp_native)) / len(pickmeapp_orders) * 100,
                                                    2) if pickmeapp_orders else "NA",
            "all_users": Passenger.objects.count(),
            "new_users": new_passengers,
            "new_credit_card_users": new_billing_info,
            #            "new_credit_card_users": len(filter(lambda p: hasattr(p, "billing_info"), new_passengers)),
            "all_credit_card_users": BillingInfo.objects.count(),
            "average_sharing": round(float(len(shared_rides_with_sharing)) / len(shared_rides) * 100,
                                     2) if shared_rides else "No Shared Rides",
            "shared_rides": len(shared_rides) if shared_rides else "No Shared Rides",
            "income": round(sum([bt.amount for bt in all_trx]), 2),
            "expenses": sum([sr.value for sr in shared_rides])
        }

        for key, val in data.iteritems():
            try:
                if type(val) == int:
                    data[key] = format_number(value=val, places=0, dp='')
                elif type(val) == float:
                    data[key] = format_number(value=str(val))
            except Exception, e:
                logging.error("format error: %s" % e)

        return data

    data = None
    try:
        data = f()
    except:
        async_computation_failed_signal.send(sender="kpi", channel_id=channel_id)

    async_computation_completed_signal.send(sender="kpi", channel_id=channel_id, data=data, token=token)


@staff_member_required
def birdseye_view(request):
    na = "N/A"
    init_start_date = default_tz_now_min()
    init_end_date = default_tz_now_max() + timedelta(days=7)
    order_status_labels = [label for (key, label) in ORDER_STATUS]

    def f(start_date, end_date):
        computations = RideComputation.objects.filter(hotspot_datetime__gte=start_date, hotspot_datetime__lte=end_date)
        departing = filter(lambda rc: rc.hotspot_type == StopType.PICKUP, computations)
        arriving = filter(lambda rc: rc.hotspot_type == StopType.DROPOFF, computations)
        data = []

        for c in sorted(computations, key=lambda c: c.hotspot_datetime, reverse=True):
            time = c.hotspot_datetime
            orders_data = [{'id': o.id,
                            'from': o.from_raw,
                            'to': o.to_raw,
                            'passenger_name': "%s %s" % (o.passenger.user.first_name,
                                                         o.passenger.user.last_name) if o.passenger and o.passenger.user else na
                ,
                            'passenger_phone': o.passenger.phone if o.passenger else na,
                            'type': OrderType.get_name(o.type),
                            'status': o.get_status_label(),
                            'debug': 'debug' if o.debug else ''
            }
            for o in c.orders.all()]

            status = RideComputationStatus.get_name(c.status)
            if c.status == RideComputationStatus.PENDING and c.submit_datetime:
                status = "%s@%s" % (status, c.submit_datetime.strftime("%H:%M"))
            c_data = {'id': c.id,
                      'status': status,
                      'time': time.strftime("%d/%m/%y, %H:%M"),
                      'dir': 'Hotspot->' if c.hotspot_type == StopType.PICKUP else '->Hotspot' if c.hotspot_type == StopType.DROPOFF else na,
                      'orders': orders_data,
                      }

            data.append(c_data)
        return data

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