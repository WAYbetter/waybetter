from google.appengine.api.taskqueue import taskqueue
from django.core.urlresolvers import reverse
from django.views.decorators.csrf import csrf_exempt
from common.decorators import catch_view_exceptions, internal_task_on_queue
from common.util import notify_by_email
from common.route import calculate_time_and_distance
from django.http import HttpResponse


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
    for i, p in enumerate(TEL_AVIV_POINTS):
        q = TEL_AVIV_POINTS[(i+1) % l]
        result = calculate_time_and_distance(p["lon"], p["lat"], q["lon"], q["lat"])
        if not (result["estimated_distance"] and result["estimated_duration"]):
            err_msg += "calculate_time_and_distance failed for: p=(%s, %s), q=(%s, %s)\n" % (p["lon"], p["lat"], q["lon"], q["lat"])
            success= False

    if not success:
        notify_by_email("uh oh, routing service may be down", err_msg)

    return HttpResponse("OK")

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