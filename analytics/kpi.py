# This Python file uses the following encoding: utf-8
import calendar
import gzip
import pickle
from google.appengine.ext.deferred import deferred
from common.signals import async_computation_failed_signal, async_computation_completed_signal
from billing.enums import BillingStatus
from billing.models import BillingTransaction, BillingInfo
from common.util import    send_mail_as_noreply
from common.tz_support import  default_tz_now, set_default_tz_time, default_tz_now_min, default_tz_now_max
from ordering.models import  RideComputation, OrderType, Order, CHARGED, ACCEPTED, APPROVED, REJECTED, TIMED_OUT, FAILED, Passenger, SharedRide, Station, RideComputationStatus
import datetime
import logging
from sharing.models import HotSpotPopularityRule

CSV_SEP = ";"
LIST_SEP = ","
CSV_RECIPIENT = "amir@waybetter.com"

def write_csv_line(csv, list_of_values):
    for i, val in enumerate(list_of_values):
        if isinstance(val, (set, list)):
            list_of_values[i] = LIST_SEP.join([unicode(e) for e in val])

    csv += CSV_SEP.join([unicode(v).replace(CSV_SEP, "") for v in list_of_values])
    csv += u"\n"
    return csv

def v1_VS_v1_1_csv(hotspot):
    pass

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


def calc_kpi3(start_index=0, two_address=0, single_address=0, order_count=0):
    logging.info("calc_kpi3: starting at: %d" % start_index)

    orders = Order.objects.filter(type=OrderType.PICKMEAPP)[start_index:]
    first = False
    order = None
    try:
        for o in orders:
            order = o
            if not first:
                logging.info("First order = %s" % o)
                first = True

            order_count += 1

            if o.from_raw and o.to_raw:
                two_address += 1
            else:
                single_address +=1
    except :
        logging.info("DB timeout raised after %d\nlast order = %s" % (order_count, order))
        deferred.defer(calc_kpi3, start_index=order_count, two_address=two_address, single_address=single_address, order_count=order_count)

    if orders:
        deferred.defer(calc_kpi3, start_index=order_count, two_address=two_address, single_address=single_address, order_count=order_count)
    else:
#    send_mail_as_noreply("guy@waybetter.com", "KPIs", attachments=[("kpis.csv", csv_file)])
        send_mail_as_noreply("guy@waybetter.com", "KPIs - Order Addresses", msg="count=%d, single=%d, double=%d" % (order_count, single_address, two_address))


def calc_kpi2(r):
    data = [["Month", "New Users", "Active Users", "Avg. Rides per User", "Avg. Occupancy", "Stickiness", "Income"]]
    for month_offset in xrange(0,r):
        logging.info("kpi for %s" % month_offset)
        def get_query_date_range_by_month_offset(month_offset):
            now = default_tz_now()
            if now.month > month_offset:
                d = now.replace(month=now.month - month_offset)
            else:
                d = now.replace(month=now.month - month_offset + 12, year=now.year -1)


            start_day, end_day = calendar.monthrange(d.year, d.month)

            start_date = default_tz_now_min().replace(day=1, month=d.month, year=d.year)
            end_date = default_tz_now_max().replace(day=end_day, month=d.month, year=d.year)

            return start_date, end_date

        start_date, end_date = get_query_date_range_by_month_offset(month_offset)

        rides = SharedRide.objects.filter(create_date__gte=start_date, create_date__lte=end_date, debug=False)
        all_bi = BillingInfo.objects.filter(create_date__gte=start_date, create_date__lte=end_date)
        new_passengers = set()
        income  = 0

        for bi in all_bi:
            try:
                p = bi.passenger
                new_passengers.add(p)
            except Passenger.DoesNotExist:
                pass

        active_passengers = set()
        number_of_people_in_rides = 0
        for ride in rides:
            orders = ride.orders.all()
            for o in orders:
                try:
                    p = o.passenger
                    active_passengers.add(p)
                except Passenger.DoesNotExist:
                    pass

                number_of_people_in_rides += o.num_seats

                income += sum([bt.amount for bt in o.billing_transactions.all()])

        sticky_passengers = set()
        for a_p in active_passengers:
            prev_orders = Order.objects.filter(passenger=a_p, depart_time__lte=start_date, type=OrderType.SHARED, status__in=[APPROVED, ACCEPTED, CHARGED]).order_by("-depart_time") # sorting to re-use existing index
            if prev_orders:
                sticky_passengers.add(a_p)

        line = [
            end_date.strftime("%m/%d/%Y"), # prepared for google docs trend chart
            len(new_passengers),
            len(active_passengers),
            len(rides) / float(len(active_passengers)) if len(active_passengers) else "NA",
            number_of_people_in_rides / float(len(rides)) if len(rides) else "NA",
            len(sticky_passengers) / float(len(active_passengers)) * 100 if len(active_passengers) else "NA",
            income / float(1000)
        ]
        data.append(line)

    csv_file = ""
    for line in data:
        logging.info("line = %s" % line)

        line = [round(i, 2) if isinstance(i, float) else i for i in line]
        csv_file += u",".join([unicode(i) for i in line])
        csv_file += "\n"

    send_mail_as_noreply("guy@waybetter.com", "KPIs", attachments=[("kpis.csv", csv_file)])


def calc_ny_sharing(offset=0, count=0, value=0):
    batch_size = 500
    logging.info("querying shared rides %s->%s" % (offset, offset + batch_size))
    s = Station.by_id(1529226)
    shared_rides = SharedRide.objects.filter(station=s)[offset: offset + batch_size]
    for sr in shared_rides:
        count += 1
        value += sr.value

    if shared_rides:
        deferred.defer(calc_ny_sharing, offset=offset + batch_size + 1, count=count, value=value)
    else:
        logging.info("all done, sending report")
        send_mail_as_noreply("guy@waybetter.com", "Shared rides data for NY", msg="count=%d, value=%f" % (count, value))


def calc_order_timing(offset=0, hours=None):
    if not hours: hours = {}
    batch_size = 500
    logging.info("querying shared rides %s->%s" % (offset, offset + batch_size))
    orders = Order.objects.filter(type=OrderType.PICKMEAPP)[offset: offset + batch_size]
    for o in orders:
        hour = str(o.create_date.hour)
        if hour in hours:
            hours[hour] += 1
        else:
            hours[hour] = 1

    if orders:
        deferred.defer(calc_order_timing, offset=offset + batch_size + 1, hours=hours)
    else:
        logging.info("all done, sending report\n%s" % hours)
        csv = ",".join(hours.keys()) + "\n" + ",".join([str(v) for v in hours.values()])
        send_mail_as_noreply("guy@waybetter.com", "Shared rides data for NY", attachments=[("order_timing.csv", csv)])


def calc_order_per_day_pickmeapp(offset=0, data=None):
    if not data: data = {"avg": 0, "count": 0}
    batch_size = 500
    days_threshold = 3
    logging.info("querying passengers %s->%s" % (offset, offset + batch_size))
    passengers = Passenger.objects.all()[offset: offset + batch_size]

    for p in passengers:
        skip_passenger = False
        orders = list(Order.objects.filter(passenger=p, type=OrderType.PICKMEAPP))
        orders = filter(lambda o: not o.debug, orders)
        orders = sorted(orders, key=lambda o: o.create_date)
        if len(p.phone) != 10 or (not p.phone.startswith("05")):
            skip_passenger = True

        if len(orders) < 2:
#            logging.info("skipping passenger[%s]: not enough orders (%d)" % (p.id, len(orders)))
            skip_passenger = True

        if not skip_passenger:
            used_days = {}
            for o in orders:
                day = o.create_date.strftime("%Y/%m/%d")
                if day in used_days:
                    if used_days[day] >= days_threshold:
                        logging.info("skipping passenger[%s]: too many orders per day: %s" % (p.id, day))
                        skip_passenger = True
                        break
                    else:
                        used_days[day] += 1
                else:
                    used_days[day] = 1


        if skip_passenger:
            continue

        first_order = orders[0]
        last_order = orders[-1]

        td = (last_order.create_date - first_order.create_date)
        interval = td.days
        if interval < 3: continue


#        if not interval:
#            if td.seconds >= 60 * 15:
#                interval += td.seconds / 60.0 / 60.0 / 24.0

        if interval:
            avg = len(orders) / float(interval)
            data["avg"] = (data["avg"] * data["count"] + avg) / float(data["count"] + 1)
            data["count"] += 1
            logging.info("avg for passenger: %s is %f (orders=%d, interval=%f)\ndata=%s" % (p, avg, len(orders), interval, data))
        else:
            logging.info("skipping passenger[%s]: interval=0 for orders[%s, %s]" % (p.id, first_order, last_order))

    if passengers:
        logging.info("continue to next batch: %s" % data)
        deferred.defer(calc_order_per_day_pickmeapp, offset=offset + batch_size + 1, data=data)
    else:
        logging.info("all done, sending report\n%s" % data)
        send_mail_as_noreply("guy@waybetter.com", "Order freq - pickmeapp", msg="%s" % data)


def calc_pickmeapp_passenger_count(offset=0, count=0):
    batch_size = 500
    logging.info("querying passengers %s->%s" % (offset, offset + batch_size))
    passengers = Passenger.objects.all()[offset: offset + batch_size]
    for p in passengers:
        pickemapp_orders = p.orders.filter(type=OrderType.PICKMEAPP)
        if pickemapp_orders:
            count +=1

    if passengers:
        logging.info("continue to next batch: %s" % count)
        deferred.defer(calc_pickmeapp_passenger_count, offset=offset + batch_size + 1, count=count)
    else:
        logging.info("all done, sending report\n%s" % count)
        send_mail_as_noreply("guy@waybetter.com", "Passenger count - pickmeapp", msg="count = %s" % count)


def calc_station_rating(offset=0, data=None):
    if not data: data = {}

    batch_size = 500
    logging.info("querying orders %s->%s" % (offset, offset + batch_size))
    orders = Order.objects.filter(type=OrderType.PICKMEAPP)[offset: offset + batch_size]
    for o in orders:
        if not o.station: continue
        if not o.passenger_rating: continue

        station_name = o.station.name
        if station_name in data:
            count, avg = data[station_name]
            avg = (count*avg + o.passenger_rating) / float(count+1)
            count += 1
            data[station_name] = (count, avg)
        else:
            data[station_name] = (1, o.passenger_rating)

    if orders:
        deferred.defer(calc_station_rating, offset=offset + batch_size + 1, data=data)
    else:
        logging.info("all done, sending report\n%s" % data)
        csv = [["Station Name", "Ratings", "Avg"]]
        for s in data.keys():
            csv.append([s, data[s][0], data[s][1]])
        csv_string = ""
        logging.info("csv = %s" % csv)
        for line in csv:
            csv_string += ",".join(line) + "\n"

        send_mail_as_noreply("guy@waybetter.com", "Shared rides data for NY", attachments=[("stations_ratings.csv", csv_string)])


def calc_passenger_ride_freq(offset=0, data=None):
    if not data:
        data = [["id", "orders", "days"]]
    else:
        data = pickle.loads(gzip.zlib.decompress(data))

    batch_size = 500
    logging.info("querying passengers %s->%s" % (offset, offset + batch_size))
    passengers = Passenger.objects.all()[offset: offset + batch_size]

    for p in passengers:
        try:
            bi = p.billing_info
        except BillingInfo.DoesNotExist:
            continue

        days = (default_tz_now() - bi.create_date).days
        if days:
            orders = list(Order.objects.filter(passenger=p, type__in=[OrderType.SHARED, OrderType.PRIVATE]))
            orders = filter(lambda o: o.ride, orders)
            data.append([p.id, len(orders), days])

    if passengers:
        data = gzip.zlib.compress(pickle.dumps(data), 9)
        deferred.defer(calc_passenger_ride_freq, offset=offset + batch_size + 1, data=data)
    else:
        logging.info("all done, sending report\n%s" % data)
        csv_string = ""
        for line in data:
            csv_string += ",".join([str(i) for i in line]) + "\n"

        send_mail_as_noreply("guy@waybetter.com", "Passenger ride freq", attachments=[("passenger_freq.csv", csv_string)])


def calc_passenger_rides(offset=0, data=None):
    if not data: data = {"active":0, "non-active": 0}
    batch_size = 500
    logging.info("querying passengers %s->%s" % (offset, offset + batch_size))
    passengers = Passenger.objects.all()[offset: offset + batch_size]

    for p in passengers:
        try:
            bi = p.billing_info
        except BillingInfo.DoesNotExist:
            continue

        orders = list(Order.objects.filter(passenger=p, type__in=[OrderType.SHARED, OrderType.PRIVATE]))
        if not orders:
            continue

        active = False
        for o in orders:
            if o.ride:
                active = True
                break

        if active:
            data["active"] += 1
        else:
            data["non-active"] += 1


    if passengers:
        deferred.defer(calc_passenger_rides, offset=offset + batch_size + 1, data=data)
    else:
        logging.info("all done, sending report\n%s" % data)
        send_mail_as_noreply("guy@waybetter.com", "passenger rides", msg="%s" % data)


def calc_passenger_order_freq(offset=0, data=None):
    if not data: data = {"7": 0, "14":0, "30": 0, "longer": 0, "avg": 0, "count": 0}
    batch_size = 500
    logging.info("querying passengers %s->%s" % (offset, offset + batch_size))
    passengers = Passenger.objects.all()[offset: offset + batch_size]

    for p in passengers:
        orders = list(Order.objects.filter(passenger=p, type__in=[OrderType.SHARED, OrderType.PRIVATE]))
        orders = sorted(orders, key=lambda o: o.create_date)
        orders = filter(lambda o: o.ride, orders)
        for i, o in enumerate(orders):
            if len(orders) > i + 1:
                td = orders[i + 1].create_date - o.create_date
                days = td.days
                if not days:
                    days = td.seconds / 60.0 / 60.0 / 24.0

                data["avg"] = (data["avg"] * data["count"] + days) / float(data["count"] + 1)
                data["count"] += 1

                if days <= 7:
                    data["7"] += 1
                elif days <= 14:
                    data["14"] += 1
                elif days <= 30:
                    data["30"] += 1
                else:
                    data["longer"] += 1

    if passengers:
        deferred.defer(calc_passenger_order_freq, offset=offset + batch_size + 1, data=data)
    else:
        logging.info("all done, sending report\n%s" % data)
        send_mail_as_noreply("guy@waybetter.com", "Order freq", msg="%s" % data)
