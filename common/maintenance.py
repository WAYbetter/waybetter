# This Python file uses the following encoding: utf-8
from google.appengine.api import memcache
from google.appengine.api.taskqueue import taskqueue, DuplicateTaskNameError, TaskAlreadyExistsError, TombstonedTaskError
from google.appengine.api.urlfetch import fetch
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.http import  HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from google.appengine.ext.deferred import deferred
from billing.billing_manager import get_token_url
from common.fax.backends.google_cloud_print import GoogleCloudPrintBackend
from common.tz_support import default_tz_time_min, default_tz_now, set_default_tz_time
from common.util import has_related_objects, url_with_querystring, get_unique_id, send_mail_as_noreply
from common.decorators import catch_view_exceptions, internal_task_on_queue
from common.util import notify_by_email
from common.route import calculate_time_and_distance
from django.contrib.sessions.models import Session
from ordering.models import  Order, Passenger, OrderAssignment, SharedRide, TaxiDriverRelation, RideEvent
from djangoappengine.db.utils import get_cursor, set_cursor
import logging
import traceback
import datetime

TEL_AVIV_POINTS = [
    #        {'lat': 32.09174, 'lon': 34.777443}, {'lat': 32.090103, 'lon': 34.777744},
    #        {'lat': 32.090546, 'lon': 34.78028}, {'lat': 32.088547, 'lon': 34.776436},
    #        {'lat': 32.082596, 'lon': 34.7732}, {'lat': 32.079086, 'lon': 34.770794},
    #        {'lat': 32.07664, 'lon': 34.77032}, {'lat': 32.07427, 'lon': 34.768784},
    #        {'lat': 32.081547, 'lon': 34.77568}, {'lat': 32.09119, 'lon': 34.775223},
    #        {'lat': 32.06314, 'lon': 34.76669}, {'lat': 32.070816, 'lon': 34.768723},
    #        {'lat': 32.060783, 'lon': 34.79574}, {'lat': 32.055943, 'lon': 34.793587},
    #        {'lat': 32.058353, 'lon': 34.79518}, {'lat': 32.0557, 'lon': 34.789036},
    #        {'lat': 32.04155, 'lon': 34.80973}, {'lat': 32.051052, 'lon': 34.79064},
    #        {'lat': 32.080517, 'lon': 34.787476}, {'lat': 32.074303, 'lon': 34.784668},
    #        {'lat': 32.062687, 'lon': 34.77778}, {'lat': 32.067154, 'lon': 34.776863},
    #        {'lat': 32.055916, 'lon': 34.77605}, {'lat': 32.05384, 'lon': 34.77084},
    #        {'lat': 32.053658, 'lon': 34.77749}, {'lat': 32.067436, 'lon': 34.77973},
        {'lat': 32.052353, 'lon': 34.765686}, {'lat': 32.046623, 'lon': 34.75981},
        {'lat': 32.039978, 'lon': 34.754578}, {'lat': 32.049164, 'lon': 34.76661},
        {'lat': 32.068073, 'lon': 34.797314}, {'lat': 32.070858, 'lon': 34.794914},
        {'lat': 32.065464, 'lon': 34.794945}, {'lat': 32.045906, 'lon': 34.779137},
        {'lat': 32.049862, 'lon': 34.778362}, {'lat': 32.051308, 'lon': 34.78001},
        {'lat': 32.052517, 'lon': 34.77616}, {'lat': 32.071724, 'lon': 34.77596},
        {'lat': 32.069763, 'lon': 34.766605}, {'lat': 32.11959, 'lon': 34.80381},
        {'lat': 32.122944, 'lon': 34.80054}, {'lat': 32.113266, 'lon': 34.79961},
        {'lat': 32.112648, 'lon': 34.833992}, {'lat': 32.111465, 'lon': 34.8335},
        {'lat': 32.108658, 'lon': 34.83316}, {'lat': 32.052555, 'lon': 34.77172}]



class Mapper(object):
    QUERY = None

    def map(self, entity):
        pass

    def run(self, start=None, batch_size=100, count=0):
        logging.info("Mapper run start at: %s" % count)
        if start:
            logging.info("start cursor = %s" % start)
            q = set_cursor(self.QUERY, start)
        else:
            q = self.QUERY

        entities = q[0:batch_size]
        try:
            end_cursor = get_cursor(entities)
        except :
            logging.error(traceback.format_exc())
            return

        for entity in entities:
            logging.info("Mapper entity: %s" % entity)
            count += 1
            self.map(entity)

        if entities:
            deferred.defer(self.run, start=end_cursor, count=count, _queue="maintenance")

class BIEventMapper(Mapper):
    from analytics.models import BIEvent

    QUERY = BIEvent.objects.all()
    def map(self, entity):
        from common.middleware.minidetector import search_strings
        if entity.user_agent:
            s = entity.user_agent.lower()
            entity.mobile = False
            for ua in search_strings:
                if ua in s:
                    entity.mobile = True

            entity.save()
            logging.info("event.mobile = %s" % entity.mobile)

@catch_view_exceptions
def fleet_manager_test(request):
    """
    Currently this serves as a "keep-alive" hack that keeps our server's ISRClient connected to ISR and resolves all
    kinds of connectivity issues.
    """
    from fleet.backends.isr_proxy import ISRProxy
    return HttpResponse(ISRProxy.is_ok())

def build_places(csv_path):
    import csv
    from geo.models import Place
    from common.models import Country, City
    from django.conf import settings

    israel = Country.objects.get(code=settings.DEFAULT_COUNTRY_CODE)
    ta = City.objects.get(name="תל אביב יפו")
    reader = csv.reader(open(csv_path), delimiter=",")
    for row in reader:
        if len(row) == 4:
            place = Place()
            place.lon = row[0]
            place.lat = row[1]
            place.name = row[2]
            place.description = row[3]
            place.country = israel
            place.city = ta
            place.save()
            logging.info("new place created: %s" % row)
        else:
            logging.info("skipping row: %s" % row)


@catch_view_exceptions
def run_billing_service_test(request):
    failures_counter = "billing_test_failures"
    max_strikes = 3

    success = True
    err_msg = ""

    try:
        for val in [False, True]:
            request.mobile = val
            url = get_token_url(request)
            result = fetch(url)
            if result.status_code != 200:
                success = False
                err_msg = "status_code: %s" % result.status_code

    except Exception, e:
        err_msg = "There was an exception: %s\nTraceback:%s" % (e, traceback.format_exc())
        success = False

    if success:
        memcache.set(key=failures_counter, value=0)
    else:
        memcache.incr(failures_counter, initial_value=0)
        if memcache.get(failures_counter) == max_strikes:
            notify_by_email("billing service appears to be down (strike #%s)" % max_strikes, err_msg)

    return HttpResponse("OK")


@catch_view_exceptions
def run_routing_service_test(request):
    task = taskqueue.Task(url=reverse(test_routing_service_task))
    q = taskqueue.Queue('maintenance')
    q.add(task)

    return HttpResponse("Task Added")


def run_gcp_service_test(request):
    task = taskqueue.Task(url=reverse(test_gcp_service_task))
    q = taskqueue.Queue('maintenance')
    q.add(task)

    return HttpResponse("Task Added")


@csrf_exempt
@catch_view_exceptions
@internal_task_on_queue('maintenance')
def test_gcp_service_task(request):
    gcp_backend = GoogleCloudPrintBackend()
    result = gcp_backend.get_printers()
    logging.info("test_gcp_service_task: %s" % result)
    if not result or not result.get("success"):
        notify_by_email("Google Cloud Print service appears to be down")

    return HttpResponse("OK")


@csrf_exempt
@catch_view_exceptions
@internal_task_on_queue('maintenance')
def test_routing_service_task(request):
    failures_counter = "routing_test_failures"
    num_strikes = 3

    l = len(TEL_AVIV_POINTS)

    success = True
    err_msg = ""
    try:
        for i, p in enumerate(TEL_AVIV_POINTS):
            q = TEL_AVIV_POINTS[(i + 1) % l]
            result = calculate_time_and_distance(p["lon"], p["lat"], q["lon"], q["lat"])
            if not (result["estimated_distance"] and result["estimated_duration"]):
                err_msg += "calculate_time_and_distance failed for: p=(%s, %s), q=(%s, %s)\n" % (
                    p["lon"], p["lat"], q["lon"], q["lat"])
                success = False
    except Exception, e:
        success = False
        err_msg = "%s\n There was an exception: %s\nTraceback:%s" % (err_msg, e, traceback.format_exc())

    if success:
        memcache.set(key=failures_counter, value=0)
    else:
        memcache.incr(failures_counter, initial_value=0)
        if memcache.get(failures_counter) == num_strikes:
            notify_by_email("routing service appears to be down (strike #%s)" % num_strikes, err_msg)

    return HttpResponse("OK")


@catch_view_exceptions
def weekly(request):
    logging.info("setup deletion of expired sessions")
    deferred.defer(delete_expired_sessions, _queue="maintenance")

    return HttpResponse("OK")


@staff_member_required
def run_maintenance_task(request):
    base_name = 'maintenance-task'
    name = request.GET.get("name", base_name)
    task = taskqueue.Task(url=reverse(maintenance_task), name=name)
    q = taskqueue.Queue('maintenance')
    response = HttpResponse("Task Added")
    try:
        q.add(task)
    except TombstonedTaskError:
        response = HttpResponseRedirect(
            url_with_querystring(reverse(run_maintenance_task), name="%s-%s" % (base_name, get_unique_id())))
    except TaskAlreadyExistsError:
        response = HttpResponse("Task not added: TaskAlreadyExistsError")
    except DuplicateTaskNameError:
        response = HttpResponse("Task not added: DuplicateTaskNameError")

    return response


@csrf_exempt
@catch_view_exceptions
@internal_task_on_queue("maintenance")
def maintenance_task(request):
    try:
        do_task()
        return HttpResponse("Done")
    except Exception, e:
        logging.error("Failed during task: %s" % e)
        return HttpResponse("Failed")


def do_task():
    # maintenance method goes here

    #fix bi events mobile property
    BIEventMapper().run()

def exec_src(src):
    try:
        code = compile(src, '', 'exec')
        exec code
    except Exception, e:
        logging.error(traceback.format_exc())


@staff_member_required
def eval_src(request):
    response = HttpResponse("Error fetching source file")

    url = request.GET.get("url")
    defer = request.GET.get("defer", False)
    res = fetch(url)

    if res and res.content:
        src = res.content.strip()
        if defer:
            response = HttpResponse("ok, will run as deferred")
            deferred.defer(exec_src, src)
        else:
            exec_src(src)
            response = HttpResponse("ok, done")

    return response


def first_ride_stats():
    csv = u""
    sharing_launched = set_default_tz_time(datetime.datetime(2011, 10, 1, 0, 0, 0))
    rides = filter(lambda ride: ride.debug == False, SharedRide.objects.filter(create_date__gte=sharing_launched))
    orders = [order for ride in rides for order in ride.orders.all()]
    sharing_passengers = set([order.passenger for order in orders])

    for passenger in sharing_passengers:
        my_orders = filter(lambda o: o.passenger == passenger, orders)
        if my_orders:
            my_first_order = sorted(my_orders, key=lambda o: o.create_date)[0]
            try:
                csv += u",".join([unicode(v) for v in
                [my_first_order.depart_time.date().isoformat(), passenger.full_name, passenger.phone]])
                csv += u"\n"
            except Exception, e:
                logging.error("order[%s]: %s" % (my_first_order.id, e.message))

    send_mail_as_noreply("amir@waybetter.com", "first rides data", attachments=[("first_ride_stats.csv", csv)])


def feb_statistics():
    sharing_launched = set_default_tz_time(datetime.datetime(2011, 10, 1, 0, 0, 0))
    feb_start = datetime.date(2012, 2, 1)
    feb_end = datetime.date(2012, 3, 1) - datetime.timedelta(days=1)

    rides = filter(lambda ride: ride.debug == False, SharedRide.objects.filter(create_date__gte=sharing_launched))
    orders = [order for ride in rides for order in ride.orders.all()]
    sharing_passengers = set([order.passenger for order in orders])

    feb_rides = []
    pre_feb_sharing_passengers = set()

    for ride in rides:
        if feb_start <= ride.create_date.date() <= feb_end:
            feb_rides.append(ride)

    feb_orders = [order for ride in feb_rides for order in ride.orders.all()]
    for order in feb_orders:
        if order.passenger.create_date.date() < feb_start:
            pre_feb_sharing_passengers.add(order.passenger)

    msg = """
    total sharing passengers: %s
    total orders: %s
    orders in february: %s
    passengers registered before feb 1st and ordered in feb: %s
    """ % (len(sharing_passengers), len(orders), len(feb_orders), len(pre_feb_sharing_passengers))
    send_mail_as_noreply("amir@waybetter.com", "feb stats", msg)


def delete_expired_sessions(start_at=0):
    now = default_tz_now()
    expired = Session.objects.filter(expire_date__lte=now)

    logging.info("start_at: %s" % start_at)
    stop_at = start_at
    try:
        for session in expired:
            session.delete()
            stop_at += 1

    except Exception, e:
        logging.info("stop_at: %s (%s deleted this run)" % (stop_at, (stop_at - start_at)))
        deferred.defer(delete_expired_sessions, stop_at, _queue="maintenance")
        return

    logging.info("total deleted: %s" % stop_at)


def generate_passengers_list():
    jan_first = datetime.datetime.combine(datetime.date(2012, 1, 1), default_tz_time_min())
    rides = SharedRide.objects.filter(depart_time__gte=jan_first)

    passengers = []
    for ride in rides:
        if ride.debug:
            continue
        for o in ride.orders.all():
            if o.passenger.create_date > jan_first:
                passengers.append(o.passenger)

    passengers = set(passengers)

    csv = u""
    for p in passengers:
        user = p.user
        csv += u",".join([user.email, user.get_full_name()])
        csv += u"\n"

    send_mail_as_noreply("amir@waybetter.com", "passengers list", attachments=[("passengers.csv", csv.encode("utf-8"))])


def measure_count():
    logging.info("Passenger.objects.count()")
    logging.info(Passenger.objects.count())
    logging.info("Passenger.objects.all().count()")
    logging.info(Passenger.objects.all().count())


# maintenance methods
def create_passenger_dup_phones():
    phones_counter = {}
    for p in Passenger.objects.all():
        phone = p.phone
        if phone in phones_counter:
            phones_counter[phone] += 1
        else:
            phones_counter[phone] = 1

    dup_phones = []
    for phone, val in phones_counter.iteritems():
        if val > 1:
            dup_phones.append(phone)

    notify_by_email("Dup phones list", str(dup_phones))


def fix_driver_taxi():
    for relation in TaxiDriverRelation.objects.all():
        try:
            logging.info("fixing taxidriver relation %d" % relation.id)
            driver = relation.driver
            taxi = relation.taxi
        except:
            relation.delete()

    for ride in SharedRide.objects.all():
        try:
            logging.info("fixing ride %d" % ride.id)
            driver = ride.driver
            taxi = ride.taxi
        except:
            ride.driver = None
            ride.station = None
            ride.save()

    logging.info("DONE")


def delete_shared_orders(ids=None):
    if ids:
        rides = SharedRide.objects.filter(id__in=ids)
    else:
        rides = SharedRide.objects.all()
    for ride in rides:
        logging.info("deleting ride %d" % ride.id)
        ride.orders.all().delete()
        ride.points.all().delete()
        ride.delete()


def denormalize_order_assignments():
    for oa in OrderAssignment.objects.all():
        if oa.dn_from_raw:
            continue # is normalized

        if hasattr(oa, 'business_name'):
            oa.dn_business_name = oa.business_name
            oa.business_name = None

        try:
            oa.save()
            logging.info("denormalizing assignment [%d]" % oa.id)
        except Order.DoesNotExist:
            oa.delete()
        except Passenger.DoesNotExist:
            pass
        except Exception, e:
            logging.error("FAILED denormalizing assignment [%d]: %s" % (oa.id, e))

    logging.info("task finished")


def generate_dead_users_list():
    list = ""
    for user in User.objects.all():
        if has_related_objects(user):
            user_link = '<a href="http://www.waybetter.com/admin/auth/user/%d/">%d</a>' % (user.id, user.id)
            list += "user [%s]: %s<br/>" % (user.username, user_link)

    notify_by_email("Dead users list", html=list)


def generate_passengers_with_non_existing_users():
    passengers_list = ""
    for passenger in Passenger.objects.all():
        try:
            passenger.user
        except:
            passenger_link = '<a href="http://www.waybetter.com/admin/ordering/passenger/%d/">%d</a>' % (
                passenger.id, passenger.id)
            passengers_list += "passenger [%s]: %s<br/>" % (passenger.phone, passenger_link)

    notify_by_email("Passengers linked to users which do not exist", html=passengers_list)


def fix_orders_house_number():
    import re

    for order in Order.objects.all():
        if not getattr(order, "from_house_number"):
            logging.info("processing order %d" % order.id)
            numbers = re.findall(r"\b(\d+)\b", order.from_raw)
            house_number = numbers[0] if numbers else 1
            order.from_house_number = house_number
            try:
                order.save()
            except Exception, e:
                logging.error("Could not save order: %d: %s" % (order.id, e.message))


def remove_duplicate_ride_events(start=0):
    def _get_key(event):
        return "%s_%s_%s_%s" % (event.lon, event.lat, event.shared_ride_id, event.raw_status)

    batch_size = 100
    end = start + batch_size

    logging.info("remove_duplicate_ride_events: processing %s->%s" % (start, end))

    events = RideEvent.objects.all()[start: end]

    for event in events:
        d = {}
        event_key = _get_key(event)
        candidate_events = RideEvent.objects.filter(lat=event.lat)
        for candidate in candidate_events:
            candidate_key = _get_key(candidate)
            if candidate_key in d:
                d[candidate_key].append(candidate)
            else:
                d[candidate_key] = [candidate]

        duplicate_events = sorted(d[event_key], key=lambda e: e.create_date)
        if len(duplicate_events) > 1:
            logging.info("deleting duplicated events of: %s" % duplicate_events[0])

        for duplicate in duplicate_events[1:]:
            logging.info("deleting: %s" % duplicate)
            duplicate.delete()

    if events:
        deferred.defer(remove_duplicate_ride_events, start=end, _queue="maintenance")
    else:
        logging.info("ALL DONE AT %s" % end)
