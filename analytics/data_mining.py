# This Python file uses the following encoding: utf-8

from common.models import CityArea
from common.util import send_mail_as_noreply
from common.tz_support import set_default_tz_time, default_tz_time_min, default_tz_time_max
from ordering.models import RideComputation, OrderType, Order, CHARGED, APPROVED, CANCELLED, SharedRide, RideComputationStatus, StopType
from sharing.models import  HotSpot
import datetime
import calendar
import logging

CSV_SEP = ";"
LIST_SEP = ","
CSV_RECIPIENT = "amir@waybetter.com"

PILOT_STARTED = set_default_tz_time(datetime.datetime(2011, 11, 1))
V1_1_STARTED = set_default_tz_time(datetime.datetime(2012, 6, 17))
now = set_default_tz_time(datetime.datetime(2012, 7, 25))

def write_csv_line(csv, list_of_values):
    for i, val in enumerate(list_of_values):
        if isinstance(val, (set, list)):
            list_of_values[i] = LIST_SEP.join([unicode(e) for e in val])

    csv += CSV_SEP.join([unicode(v).replace(CSV_SEP, "") for v in list_of_values])
    csv += u"\n"
    return csv


def sharing_breakdown():
    day_sharing = {}
    time_sharing = {}
    area_sharing = {}
    area_total = {}
    occupancy = {2: 0, 3: 0}

    areas = list(CityArea.objects.all())

    def inc_key(dict, key, amount=1):
        if dict.has_key(key):
            dict[key] += amount
        else:
            dict[key] = amount

    def compute(computations):
        for c in computations:
            if c.debug:
                continue
            if c.status != RideComputationStatus.COMPLETED:
                continue

            rides = list(c.rides.all())
            orders = [order for ride in rides for order in ride.orders.all()]

            # only count ramat hachayal
            concat_address = "_".join(["%s_%s" % (o.from_raw, o.to_raw) for o in orders])
            if concat_address.find(u"הברזל") < 0:
                continue

            ride_points = []
            for ride in rides:
                points = ride.points.filter(type=StopType.PICKUP) if c.hotspot_type == StopType.DROPOFF else ride.points.filter(type=StopType.DROPOFF)
                ride_points += list(points)

            for p in ride_points:
                for area in areas:
                    if area.contains(p.lat, p.lon):
                        inc_key(area_total, area.name)
                        break


            shared_rides = []
            for ride in rides:
                orders_count = ride.orders.count()
                if orders_count > 1:
                    shared_rides.append(ride)
                    inc_key(occupancy, orders_count)

            if not shared_rides:
                continue

            day = c.hotspot_datetime.date()
            # we count everything as pickup times
            if c.hotspot_type == StopType.PICKUP:
                interval = c.hotspot_datetime.time()
            else:
                interval = (c.hotspot_datetime - datetime.timedelta(minutes=30)).time()

            num_shared_rides = len(shared_rides)
            inc_key(day_sharing, day.strftime("%A"), amount=num_shared_rides)
            inc_key(time_sharing, interval, amount=num_shared_rides)

            shared_points = []
            for ride in shared_rides:
                points = ride.points.filter(type=StopType.PICKUP) if c.hotspot_type == StopType.DROPOFF else ride.points.filter(type=StopType.DROPOFF)
                shared_points += list(points)

            for p in shared_points:
                for area in areas:
                    if area.contains(p.lat, p.lon):
                        inc_key(area_sharing, area.name)
                        break

    offset = 0
    batch_size = 400
    while True:
        logging.info(offset)
        computations = RideComputation.objects\
        .filter(hotspot_datetime__gte=PILOT_STARTED, hotspot_datetime__lte=now)[offset:offset + batch_size]
        if computations:
            compute(computations)
            offset += batch_size
        else:
            logging.info("done!")
            break


    for d_name in ['day_sharing', 'time_sharing', 'area_sharing', 'area_total', 'occupancy']:
        logging.info(d_name)
        logging.info(locals()[d_name])

    content = u""
    for d_name in ['day_sharing', 'time_sharing', 'area_sharing', 'area_total', 'occupancy']:
        content += "%s\n" % d_name
        for k, v in locals()[d_name].items():
            content += u"%s;%s\n" % (unicode(k), unicode(v))

        content += "\n"

    send_mail_as_noreply(CSV_RECIPIENT, "sharing breakdown", content)



def monthly_summary():
    start = PILOT_STARTED
    end = start.replace(day=calendar.monthrange(start.year, start.month)[1])
    end = datetime.datetime.combine(end.date(), default_tz_time_max())

    money_data = {}
    passenger_data = {}
    while end <= now:
        logging.info("%s -> %s" % (start, end))
        rides = SharedRide.objects.filter(create_date__gte=start, create_date__lte=end, debug=False)
        orders = [order for ride in rides for order in ride.orders.all()]
        expense = sum([ride.cost for ride in rides])
        income = sum([order.price for order in orders])
        money_data[start.strftime("%d/%m/%Y")] = [expense, income]

        # filter only ramat hachyal orders
        f = lambda o: "_".join(["%s_%s" % (o.from_raw, o.to_raw)]).find(u"הברזל") > 0
        ramat_hachayal_orders = filter(f, orders)
        passengers = set([o.passenger for o in ramat_hachayal_orders])
        for p in passengers:
            p_orders = filter(lambda o: o.passenger == p, ramat_hachayal_orders)
            p_money = sum([o.price for o in p_orders])
            new_vals = [len(p_orders), p_money]

            if passenger_data.has_key(p):
                passenger_data[p] = [old + new for (old, new) in zip(passenger_data[p], new_vals)]
            else:
                passenger_data[p] = new_vals

        start = end + datetime.timedelta(days=1)
        start = datetime.datetime.combine(start.date(), default_tz_time_min())
        end = start.replace(day=calendar.monthrange(start.year, start.month)[1])
        end = datetime.datetime.combine(end.date(), default_tz_time_max())

    for passenger, data in passenger_data.items():
        numdays = (now - passenger.create_date).days
        data.append(numdays)

    money_csv = ";".join(["month", "expense", "income", "\n"])
    for month, data in money_data.items():
        money_csv += ";".join([month] + [str(d) for d in data] + ["\n"])

    passenger_csv = ";".join(["passenger", "orders", "payment", "numdays" "\n"])
    for passenger, data in passenger_data.items():
        passenger_csv += ";".join([passenger.name] + [str(d) for d in data] + ["\n"])

    send_mail_as_noreply(CSV_RECIPIENT, "monthly summary csv", "attached", attachments=[('passenger.csv', passenger_csv), ('money.csv', money_csv)])


def weekly_summary():
    first_sunday = PILOT_STARTED
    while first_sunday.weekday() != 6:
        first_sunday = first_sunday + datetime.timedelta(days=1)

    sun = datetime.datetime.combine(first_sunday.date(), default_tz_time_min())
    sat = sun + datetime.timedelta(days=6)
    sat = datetime.datetime.combine(sat.date(), default_tz_time_max())

    weekly_data = {}

    while sat < now:
        rides = SharedRide.objects.filter(create_date__gte=sun, create_date__lte=sat, debug=False)
        orders = [order for ride in rides for order in ride.orders.all()]
        passengers = set([o.passenger for o in orders])

        week_name = "%s-%s" % sun.isocalendar()[:2]
        weekly_data[week_name] = [len(rides), len(orders), len(passengers)]

        sun += datetime.timedelta(days=7)
        sat += datetime.timedelta(days=7)

    csv = ";".join(["week", "rides", "orders", "passengers", "\n"])
    for week, data in weekly_data.items():
        csv += ";".join([week] + [str(d) for d in data] + ["\n"])

    send_mail_as_noreply(CSV_RECIPIENT, "rides weekly summary", "attached", attachments=[("weekly.csv"), csv])


def pilot_orders_csv():
    start_date = PILOT_STARTED
    end_date = now
    days = {}
    data = {
        'orders': 0,
        'cancellations': 0,
        'web': 0,
        'mobile': 0,
    }
    ordering_table_v1 = {
        '0-60': 0,
        '60-180': 0,
        '180-360': 0,
        '360-720': 0,
        '720-inf': 0,
    }
    ordering_table_v1_1 = ordering_table_v1.copy()

    def compute(orders):
        for order in orders:
            if order.create_date < start_date:
                continue
            if order.debug:
                continue
            if order.status not in [CANCELLED, APPROVED, CHARGED]:
                continue

            if order.mobile:
                data['mobile'] += 1
            else:
                data['web'] += 1

            ordering_td_min = ((order.depart_time or order.arrive_time) - order.create_date).seconds / 60
            ordering_table = ordering_table_v1 if order.create_date< V1_1_STARTED else ordering_table_v1_1
            for range in ordering_table.keys():
                low, high = range.split("-")
                if float(low) <= ordering_td_min < float(high):
                    ordering_table[range] += 1

            if order.status == CANCELLED:
                data['cancellations'] += 1

            else: # means the order was carried out by the station
                data['orders'] += 1
                day = order.create_date.date().strftime("%d/%m/%Y")
                days.setdefault(day, 0)
                days[day] += 1


    offset = 0
    batch_size = 200

    while True:
        orders = Order.objects.filter(type=OrderType.SHARED)[offset:offset + batch_size]
        if orders:
            logging.info("starting at %s" % offset)
            compute(orders)
            offset += batch_size
        else:
            logging.info("done!")
            break

    content = ""
    for k,v in data.items():
        content += "%s: %s\n" % (k, v)

    content += "\nordering times:\n"
    content += "\t".join(["time", "v1", "v1_1\n"])
    for k in ordering_table_v1:
        content += "\t".join(["%s:", "%s", "%s\n"]) % (k, ordering_table_v1[k], ordering_table_v1_1[k])

    days_csv_data = write_csv_line("", ["day", "count"])
    for day, count in days.items():
        days_csv_data = write_csv_line(days_csv_data, [day, count])
    send_mail_as_noreply(CSV_RECIPIENT, "pilot_orders_csv %s - %s" % (start_date.strftime("%d/%m/%Y"), end_date.strftime("%d/%m/%Y")),
                         content, attachments=[("days_count.csv", days_csv_data)])


def v1_VS_v1_1_csv():
    # setup
    ramat_hachayl_pop = HotSpot.by_id(3540047)
    sunday = datetime.date(2012, 6, 17)
    numdays = (now - V1_1_STARTED).days

    city_areas = list(CityArea.objects.all())
    pop_rules = list(ramat_hachayl_pop.popularity_rules.all())

    start_date = V1_1_STARTED - datetime.timedelta(days=numdays)
    end_date = V1_1_STARTED + datetime.timedelta(days=numdays)

    # data
    city_areas_data = {}
    city_area_initial_values = {
        'v1_orders': 0,
        'v1_1_orders': 0,
        'v1_income': 0,
        'v1_1_income': 0,
    }

    days_data = {}
    days_initial_values = {
        'num_orders': 0,
        'num_rides': 0,
        'num_computations': 0,
        'income': 0,
        'expense': 0,
        }

    intervals_data = {}
    interval_initial_values = {
        'popularity': 0,
        'v1_orders': 0,
        'v1_income': 0,
        'v1_expense': 0,
        'v1_passengers': set(),
        'v1_num_passengers': 0,
        'v1_1_orders': 0,
        'v1_1_income': 0,
        'v1_1_expense': 0,
        'v1_1_passengers': set(),
        'v1_1_num_passengers': 0,
        }

    def compute(computations):
        for c in computations:
            if c.debug:
                continue
            if c.status != RideComputationStatus.COMPLETED:
                continue

            rides = list(c.rides.all())
            orders = [order for ride in rides for order in ride.orders.all()]
            num_orders = len(orders)

            concat_address = "_".join(["%s_%s" % (o.from_raw, o.to_raw) for o in orders])
            if concat_address.find(u"הברזל") < 0:
                continue

            day = c.hotspot_datetime.date()
            # we count everything as pickup times
            if c.hotspot_type == StopType.PICKUP:
                interval = c.hotspot_datetime.time()
            else:
                interval = (c.hotspot_datetime - datetime.timedelta(minutes=30)).time()

            version = 'v1' if c.hotspot_datetime < V1_1_STARTED else 'v1_1'

            # initialize data. beware of mutable objects dicts and sets
            day_data = days_data.get(day)
            if not day_data:
                day_data = days_initial_values.copy()

            interval_data = intervals_data.get(interval)
            if not interval_data:
                interval_data = interval_initial_values.copy()
                interval_data['v1_passengers'], interval_data['v1_1_passengers'] = set(), set()

            # counters
            day_data['num_orders'] += num_orders
            day_data['num_rides'] += len(rides)
            day_data['num_computations'] += 1
            interval_data['%s_orders' % version] += num_orders

            # passengers, income, expense, city area
            for order in orders:
                day_data['income'] += order.price
                interval_data['%s_income' % version] += order.price
                interval_data['%s_passengers' % version].add(order.passenger.id)

                city_area = None
                lat, lon = (order.from_lat, order.from_lon) if c.hotspot_type == StopType.DROPOFF else (order.to_lat, order.to_lon)
                for ca in city_areas:
                    if ca.contains(lat, lon):
                        city_area = ca
                        break
                if city_area:
                    # area data
                    city_areas_data.setdefault(city_area.name, city_area_initial_values.copy())
                    city_areas_data[city_area.name]['%s_orders' % version] += 1
                    city_areas_data[city_area.name]['%s_income' % version] += order.price

            interval_data['%s_num_passengers' % version] = len(interval_data['%s_passengers' % version])

            for ride in rides:
                day_data['expense'] += ride.cost
                interval_data['%s_expense' % version] += ride.cost

            days_data[day] = day_data
            intervals_data[interval] = interval_data

    offset = 0
    batch_size = 300

    while True:
        computations = RideComputation.objects\
        .filter(hotspot_datetime__gte=start_date, hotspot_datetime__lte=end_date)[offset:offset + batch_size]
        if computations:
            compute(computations)
            offset += batch_size
        else:
            logging.info("done!")
            break

    # write interval data
    for interval, interval_data in intervals_data.items():
        interval_data['popularity'] = ramat_hachayl_pop.get_popularity(sunday, interval, pop_rules=pop_rules)

    intervals_csv_fields = ['popularity', 'v1_orders', 'v1_income', 'v1_expense', 'v1_num_passengers', 'v1_1_orders',
                            'v1_1_income', 'v1_1_expense', 'v1_1_num_passengers']
    intervals_csv_data = write_csv_line("", ['interval_name'] + intervals_csv_fields)
    for interval, interval_data in intervals_data.items():
        intervals_csv_data = write_csv_line(intervals_csv_data, [interval.strftime("%H:%M")] + [interval_data[title] for title in intervals_csv_fields])

    # write days data
    days_csv_fields = ['num_orders', 'num_rides', 'num_computations', 'income', 'expense']
    days_csv_data = write_csv_line("", ['day'] + days_csv_fields)
    for day, day_data in days_data.items():
        days_csv_data = write_csv_line(days_csv_data, [day.strftime("%d/%m/%Y")] + [day_data[title] for title in days_csv_fields])

    # write city area data
    areas_csv_fields = ['v1_orders', 'v1_1_orders', 'v1_income', 'v1_1_income']
    area_csv_data = write_csv_line("", ['name'] + areas_csv_fields)
    for ca_name, ca_data in city_areas_data.items():
        area_csv_data = write_csv_line(area_csv_data, [unicode(ca_name)] + [ca_data[f] for f in areas_csv_fields])


    send_mail_as_noreply(CSV_RECIPIENT, "v1 VS v1.1 report", "here is your report for %s - %s" % (start_date.strftime("%d/%m/%Y"), end_date.strftime("%d/%m/%Y")),
                         attachments=[("intervals.csv", intervals_csv_data), ("days.csv", days_csv_data), ("areas.csv", area_csv_data)])