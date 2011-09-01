from google.appengine.api.taskqueue import taskqueue, DuplicateTaskNameError, TaskAlreadyExistsError, TombstonedTaskError
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.http import  HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from common.util import has_related_objects, url_with_querystring, get_unique_id
from common.decorators import catch_view_exceptions, internal_task_on_queue
from common.util import notify_by_email
from common.route import calculate_time_and_distance
from ordering.models import  Order, Passenger, OrderAssignment, SharedRide, TaxiDriverRelation
import logging
import traceback


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


@catch_view_exceptions
def run_routing_service_test(request):
    task = taskqueue.Task(url=reverse(test_routing_service_task))
    q = taskqueue.Queue('maintenance')
    q.add(task)

    return HttpResponse("Task Added")


@csrf_exempt
@catch_view_exceptions
@internal_task_on_queue('maintenance')
def test_routing_service_task(request):
    l = len(TEL_AVIV_POINTS)

    success = True
    err_msg = ""
    try:
        for i, p in enumerate(TEL_AVIV_POINTS):
            q = TEL_AVIV_POINTS[(i + 1) % l]
            result = calculate_time_and_distance(p["lon"], p["lat"], q["lon"], q["lat"])
            if not (result["estimated_distance"] and result["estimated_duration"]):
                err_msg += "calculate_time_and_distance failed for: p=(%s, %s), q=(%s, %s)\n" % (p["lon"], p["lat"], q["lon"], q["lat"])
                success = False
    except Exception, e:
        success = False
        err_msg = "%s\n There was an exception: %s\nTraceback:%s" % (err_msg, e, traceback.format_exc())

    if not success:
        notify_by_email("uh oh, routing service may be down", err_msg)

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
    pass


# maintenance methods
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


def fix_orders():
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

