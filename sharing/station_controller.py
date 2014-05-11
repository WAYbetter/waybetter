# -*- coding: utf-8 -*-
import traceback
from common.decorators import  force_lang
from common.fax.api import send_fax, get_status, DEFAULT_BACKEND
from common.fax.backends.default import FaxStatus
from common.fax.backends.freefax import FreefaxBackend
from common.sms_notification import send_sms
from common.tz_support import  default_tz_now
from common.util import get_current_version, send_mail_as_noreply, notify_by_email, email_devs
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import logout, login
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseForbidden
from django.shortcuts import render_to_response
from django.template.context import RequestContext, Context
from django.template.loader import get_template
from django.utils import  translation
from django.views.decorators.csrf import csrf_exempt
from django.contrib.admin.views.decorators import staff_member_required
from django.core.urlresolvers import reverse
from djangotoolbox.http import JSONResponse
from google.appengine.api import channel, memcache
from google.appengine.ext import deferred
from fleet import fleet_manager
from ordering.decorators import work_station_required
from ordering.enums import RideStatus
from ordering.models import SharedRide, StopType, ACCEPTED, WorkStation, RIDE_SENTINEL_GRACE
import logging
import re
from pricing.models import RuleSet
from sharing.algo_api import CostDetails

WORKSTATION_SNAPSHOTS_NS = "WORKSTATION_SNAPSHOTS_NS"
COMMA_SPLITTER = re.compile("\s*,\s*")
STATION_PICKUP_OFFSET = timedelta(minutes=2)
FAX_ARRIVE_TIMEOUT = 5
PRINT_COMPLETE_TIMEOUT = 1

CRITICAL_MESSAGES_CONTACT_LIST = ["***REMOVED***", "***REMOVED***"] # zeev, shay

@work_station_required
@force_lang("he")
def sharing_workstation_home(request, work_station, workstation_id):
    from sharing.sharing_dispatcher import WS_SHOULD_HANDLE_TIME
    if work_station.id != int(workstation_id):
        logout(request)
        return HttpResponseRedirect(request.path)

    handle_time = WS_SHOULD_HANDLE_TIME

    channel_token = channel.create_channel(work_station.generate_new_channel_id())
    current_version = get_current_version()
    station_name = work_station.station.name

    return render_to_response('ws_home.html', locals(), context_instance=RequestContext(request))

def workstation_exit(request):
    workstation_id = request.GET.get("id")
    ws = WorkStation.by_id(workstation_id)
    if ws and not ws.station.debug:
        msg = u"%s closed the workstation module" % ws.station.name
        notify_by_email("Module Closed by Station", msg=msg)

        for num in CRITICAL_MESSAGES_CONTACT_LIST:
            send_sms(num, msg)

    return HttpResponse("OK")

@csrf_exempt
@work_station_required
def ride_viewed(request, work_station, ride_id):
    ride = SharedRide.by_id(ride_id)
    if ride and ride.station == work_station.station:
        if ride.change_status(old_status=RideStatus.ASSIGNED, new_status=RideStatus.VIEWED):
            return HttpResponse("OK")

    return HttpResponseForbidden()

@csrf_exempt
@work_station_required
def snapshot(request, work_station):
    img_data = request.POST.get("img_data")
    memcache.set(str(work_station.station_id), img_data, namespace=WORKSTATION_SNAPSHOTS_NS)

    return HttpResponse("OK")


@csrf_exempt
@work_station_required
def manual_dispatch(request, work_station, ride_id):
    ride = SharedRide.by_id(ride_id)
    taxi_number = request.POST.get("taxi_number")
    pickup_estimate = request.POST.get("pickup_estimate")
    if taxi_number and pickup_estimate and ride and ride.station == work_station.station:
        ride.taxi_number = taxi_number
        ride.pickup_estimate = int(pickup_estimate)

        fleet_manager.cancel_ride(ride)
        fleet_manager.create_ride(ride)

        ride.change_status(old_status=RideStatus.VIEWED, new_status=RideStatus.ACCEPTED)

        return HttpResponse("OK")

    return HttpResponseForbidden()

@csrf_exempt
@work_station_required
def reassign_ride(request, work_station, ride_id):
    ride = SharedRide.by_id(ride_id)
    if ride and ride.station == work_station.station:
        ride.update(taxi_number=None)
        if fleet_manager.cancel_ride(ride) and fleet_manager.create_ride(ride):
            return HttpResponse("OK")
        else:
            logging.error("could not reassign ride: %s" % ride_id)

    return HttpResponseForbidden()

def update_ride(ride):
    """
    update ride in all online workstation of assigned station
    @param ride:
    @return:
    """
    station = ride.station

    if not station:
        logging.warning("no station on update_ride")
        return # bug out

    res = {"action": "update_ride", "ride": ride.serialize_for_ws()}
    if ride.status == RideStatus.VIEWED:
        res["expand_ride"] = True

    send_update(station, res)


def send_update(station, payload):
    """
    send payload to all online, sharing workstation of station
    @param station:
    @param payload:
    """
    from ordering.station_connection_manager import _do_push

    work_stations = station.work_stations.filter(is_online=True, accept_shared_rides=True)
    logging.info("update work stations in station [%s] with payload [%s]: %s" % (station, payload, work_stations))

    for ws in work_stations:
        _do_push(ws, payload)

    if not work_stations:
        logging.warning(u"Station [%s] is offline and missed a ride update: %s" % (station.name, payload))

def remove_ride(station, ride):
    """
    removes the ride from the station module
    @param station:
    @param ride:
    """
    send_update(station, {"action": "remove_ride", "ride": ride.serialize_for_ws()})

def update_all(station):
    """
    cause the station module to sync state of all rides
    @param station:
    """
    send_update(station, {"action": "update_all"})

@work_station_required
def sharing_workstation_data(request, work_station):
    logging.info("sharing_workstation_data: %s" % work_station)

    rides_query = SharedRide.objects.filter(station=work_station.station, depart_time__lt=default_tz_now() + timedelta(hours=24), status__in=[RideStatus.ASSIGNED, RideStatus.VIEWED, RideStatus.ACCEPTED])
    rides = [r.serialize_for_ws() for r in sorted(rides_query, key=lambda ride: ride.depart_time)]

    return JSONResponse({
        'rides': rides
    })

@csrf_exempt
def workstation_auth(request):
    token = request.POST.get('token') or request.GET.get('token')
    logging.info("workstation_auth: '%s'" % token)

    try:
        workstation = WorkStation.objects.get(token=token)
    except WorkStation.DoesNotExist:
        workstation = None

    if workstation:
        result = {"status": "ok"}
        workstation.user.backend = 'django.contrib.auth.backends.ModelBackend'  # could also be fetched from the list in settings.
        login(request, workstation.user)
        if not workstation.was_installed:
            workstation.was_installed = True
            workstation.save()
    else:
        result = {"status": "failed", "token": token}


    return JSONResponse(result)

#@catch_view_exceptions # pickle complains
def send_ride_voucher(ride_id):
    ride = SharedRide.by_id(ride_id)
    if not (ride and ride.station):
        logging.error("can't send voucher ride_id=%s" % ride_id)
        return

    current_lang = translation.get_language()
    station_lang_code = settings.LANGUAGES[ride.station.language][0]
    translation.activate(station_lang_code)

    pickups = []
    dropoffs = []
    for p in sorted(ride.points.all(), key=lambda point: point.stop_time):
        orders = p.pickup_orders.all() if p.type == StopType.PICKUP else p.dropoff_orders.all()
        stop = {
            "count": sum([order.num_seats for order in orders]),
            "address": p.address
        }
        phones = ["%s - %s" % (o.passenger.name, o.passenger.phone) for o in orders]
        if len(phones) == 1:
            stop["phones"] = phones

        if p.type == StopType.PICKUP:
            pickups.append(stop)
        if p.type == StopType.DROPOFF:
            dropoffs.append(stop)

    tariff = RuleSet.get_active_set(ride.depart_time)
    srz_cost_details = CostDetails.serialize(ride.cost_details)
    template_args = {
        "ride": ride,
        "taxi": ride.taxi_number,
        "ride_date": ride.depart_time.strftime("%d/%m/%y"),
        "ride_time": (ride.first_pickup.stop_time - STATION_PICKUP_OFFSET).strftime("%H:%M"),
        "pickups": pickups,
        "dropoffs": dropoffs,
        "charged_stops": max(0, len(pickups) - 1),
        "cost_details": srz_cost_details,
        "distance": "%.1f" % float(ride.distance/1000.0) if ride.distance else "",
        "additional_km": "%.1f" % float(srz_cost_details["additional_meters"]/1000.0) if (srz_cost_details and srz_cost_details["additional_meters"]) else "",
        "tariff": tariff.name if tariff else ""
    }
    subject = "WAYBetter Ride: %s" % ride.id
    t = get_template("voucher_email.html")
    html = t.render(Context(template_args))
    # logging.info(html)

    if ride.station.vouchers_emails:
        emails = filter(lambda i: bool(i), COMMA_SPLITTER.split(ride.station.vouchers_emails))
        # let us know so we will contact the station
        resend_voucher_html = html.replace("</body>", "<br><br><a href='http://www.waybetter.com%s'>Resend Voucher</a></body>" % reverse(resend_voucher, kwargs={"ride_id": ride_id}))
        notify_by_email(u"Ride [%s] Voucher sent to %s [%s]" % (ride.id, ride.station.name, ",".join(emails)),
            html=resend_voucher_html,
            attachments=[("voucher.html", html.encode("utf-8"))])

        for email in emails:
            try:
                validate_email(email)
                send_mail_as_noreply(email, subject, html=html)
            except ValidationError:
                logging.warning(u"Strange email number: %s" % email)

    if ride.station.printer_id: # send print job to printer
        print_voucher(ride.station.printer_id, html, subject, ride_id)

    elif ride.station.fax_number: # send fax to station
        logging.warning("No printer_id defined. Sending Fax")
        fax_voucher(ride.station.fax_number, html, subject, ride_id)

    else:
        logging.info("no voucher sent for station [%s]" % ride.station)

    translation.activate(current_lang)

    logging.info("ride [%s] voucher sent" % ride.id)


@staff_member_required
def resend_voucher(request, ride_id):
    deferred.defer(send_ride_voucher, ride_id=ride_id)

    return HttpResponse("Voucher for ride [%s] will be sent" % ride_id)

# utility methods
def print_voucher(printer_id, html, title, ride_id):
    print_backend = DEFAULT_BACKEND
    logging.info(u"print_voucher: printer_id: %s" % printer_id)
    job_id = _do_voucher_send(printer_id, html, title, ride_id, print_backend, check_print_job_status)
    if not job_id:
        ride = SharedRide.by_id(ride_id)
        if ride.station.fax_number:
            notify_by_email(u"WARNING: Voucher printing failed, will try to send fax for ride: %s" % ride_id)
            logging.warning("printing failed, will send fax")
            fax_voucher(ride.station.fax_number, html, title, ride_id)
        else:
            send_ride_in_risk_notification(u"Ride voucher failed to print and station has no fax number defined.", ride_id)

def check_print_job_status(job_id, title, ride_id, html, counter=1, backend=None):
    try:
        status = get_status(job_id, backend=backend)

        logging.info("check_print_job_status(%s): '%s'" % (job_id, FaxStatus.get_name(status)))

        if status != FaxStatus.DONE:
            if counter > PRINT_COMPLETE_TIMEOUT:
                logging.info("print failure: title=%s" % title)
                ride = SharedRide.by_id(ride_id)
                if ride.station.fax_number:
                    email_devs(u"Ride voucher did not print after %d minutes: %s. (sending fax)" % (PRINT_COMPLETE_TIMEOUT, title))
                    fax_voucher(ride.station.fax_number, html, title, ride_id)
                else:
                    send_ride_in_risk_notification(u"Ride voucher did not print after %d minutes: %s.\nNo fax number defined!." % (PRINT_COMPLETE_TIMEOUT, title), ride_id)
            else:
                logging.info("print still not done: counter=%s, title=%s" % (counter, title))
                deferred.defer(check_print_job_status, job_id, title, ride_id, html, counter=counter + 1, backend=backend,
                               _countdown=60)
    except Exception, e:
        trace = traceback.format_exc()
        logging.error("check_print_job_status failed with exception: %s" % trace)
        deferred.defer(check_print_job_status, job_id, title, ride_id, html, counter=counter + 1, backend=backend, _countdown=60)

def fax_voucher(fax_number, html, title, ride_id):
    fax_backend = FreefaxBackend()
    logging.info(u"fax_voucher: fax_number: %s" % fax_number)
    job_id = _do_voucher_send(fax_number, html, title, ride_id, fax_backend, check_fax_job_status)
    if not job_id:
        send_ride_in_risk_notification(u"Voucher faxing failed", ride_id)

def _do_voucher_send(printer_or_fax, html, title, ride_id, backend, check_function):
    job_id = send_fax(printer_or_fax, html, title, backend=backend)
    logging.info("send_voucher: job_id: %s" % job_id)

    if job_id:
        deferred.defer(check_function, job_id, title, ride_id, html, backend=backend, _countdown=60) # check in 1 minute
    else:
        logging.warning("send_voucher returned no job_id for ride_id: %s" % ride_id)

    return job_id

def check_fax_job_status(fax_id, title, ride_id, html, counter=1, backend=None):
    try:
        status = get_status(fax_id, backend=backend)

        logging.info("check_fax_job_status(%s): '%s'" % (fax_id, FaxStatus.get_name(status)))

        if status != FaxStatus.DONE:
            if counter > FAX_ARRIVE_TIMEOUT:
                logging.info("fax failure: title=%s" % title)
                send_ride_in_risk_notification(u"Ride voucher fax did not arrive after %d minutes: %s." % (FAX_ARRIVE_TIMEOUT, title), ride_id)
            else:
                logging.info("fax still not done: counter=%s, title=%s" % (counter, title))
                deferred.defer(check_fax_job_status, fax_id, title, ride_id, html, counter=counter + 1, backend=backend,
                               _countdown=60)
    except Exception, e:
        trace = traceback.format_exc()
        logging.error("check_fax_job_status failed with exception: %s" % trace)
        deferred.defer(check_fax_job_status, fax_id, title, ride_id, html, counter=counter + 1, backend=backend, _countdown=60)

def ride_status_sentinel(ride_id):
    logging.info("ride_status_sentinel: %s" % ride_id)
    ride = SharedRide.by_id(ride_id)
    if ride.status != ACCEPTED:
        send_ride_in_risk_notification(
            u"Ride not accepted by station %d minutes before depart time" % (RIDE_SENTINEL_GRACE.seconds / 60), ride_id)

def send_ride_in_risk_notification(msg, ride_id):
    msg_key = u"%s_%s" % (ride_id, msg)
    namespace = "ride_in_risk_notifications"

    msg_sent = memcache.get(msg_key, namespace=namespace)
    if msg_sent:
        logging.info(u"skipping sending: %s" % msg)
        return

    ride = SharedRide.by_id(ride_id)
    if ride and ride.debug:
        logging.info("skipping notification for debug ride %s" % ride_id)

    elif ride:
        t = get_template("ride_in_risk_email.html")
        orders = ride.orders.all()
        passengers = [o.passenger for o in orders.all()]
        station = ride.station
        try:
            sharing_ws = station.work_stations.filter(accept_shared_rides=True)[0]
        except Exception:
            sharing_ws = None

        html = t.render(Context({
            "passengers": [u"%s (%s)" % (p.full_name, p.phone) for p in passengers],
            "station_phones": station.phones.all() if station else [],
            "station_name": station.name if station else "[NO STATION]",
            "online_status": sharing_ws.is_online if sharing_ws else None,
            "ride_id": ride_id,
            "depart_time": ride.depart_time.strftime("%H:%M"),
            "ride_status": RideStatus.get_name(ride.status),
            "msg": msg
        }))
        logging.info("sending risk mail: %s" % html)

        notify_by_email("IMPORTANT: Ride In Risk [%s]" % ride_id, html=html)
        memcache.set(msg_key, True, namespace=namespace)

        for num in CRITICAL_MESSAGES_CONTACT_LIST:
            send_sms(num, msg)