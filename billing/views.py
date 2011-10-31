# Create your views here.
from datetime import  date, datetime, timedelta
import logging
import csv
from billing import billing_backend
from billing.billing_backend import create_invoices
from billing.enums import BillingStatus, BillingAction
from common.tz_support import default_tz_now
from common.util import custom_render_to_response
from django.core.urlresolvers import reverse
from django.views.decorators.csrf import csrf_exempt
from billing.models import BillingForm, InvalidOperationError, BillingTransaction, BillingInfo
from common.decorators import require_parameters, internal_task_on_queue, catch_view_exceptions
from django.http import HttpResponse, HttpResponseRedirect
from django.template.context import RequestContext
from djangotoolbox.http import JSONResponse
from ordering.decorators import passenger_required_no_redirect, passenger_required
from ordering.models import SharedRide, COMPLETED, ACCEPTED, CANCELLED

def bill_passenger(request):
    form = BillingForm(data=request.POST)
    if form.is_valid():
        billing_tx = form.save()
        billing_tx.commit()

    return HttpResponse("OK")


@csrf_exempt
@catch_view_exceptions
@internal_task_on_queue("orders")
@require_parameters(method="POST", required_params=("token", "amount", "card_expiration", "billing_transaction_id", "action"))
def billing_task(request, token, amount, card_expiration, billing_transaction_id, action):
    logging.info("billing task: transaction_id=%s" % billing_transaction_id)
    action = int(action)
    if action == BillingAction.COMMIT:
        return billing_backend.do_J5(token, amount, card_expiration, billing_transaction_id)
    elif action == BillingAction.CHARGE:
        return billing_backend.do_J4(token, amount, card_expiration, billing_transaction_id)
    else:
        raise InvalidOperationError("Unknown action for billing: %s" % action)
    
@passenger_required_no_redirect
def transaction_ok(request, passenger):
    #TODO: handle errors
    #TODO: makesure referrer is creditguard
    date_string = request.GET.get("cardExp")
    exp_date = date(year=int(date_string[2:]) + 2000, month=int(date_string[:2]), day=1)
    kwargs = {
        "passenger"				: passenger,
        "token"					: request.GET.get("cardToken"),
        "expiration_date"		: exp_date,
        "card_repr"				: request.GET.get("cardMask"),
        "personal_id"          : request.GET.get("personalId")
    }
    # clean up old billing info objects
    BillingInfo.objects.filter(passenger=passenger).delete()

    # save new billing info
    billing_info = BillingInfo(**kwargs)
    billing_info.save()

    logging.info("looking for order via: %s" % request.GET.get("uniqueID"))
    order = request.session.get(request.GET.get("uniqueID"))
    if order and order.price and order.passenger == passenger:
        logging.info("Billing order: %s" % order)
        billing_trx = BillingTransaction(order=order, amount=order.price)
        billing_trx.save()
        return HttpResponseRedirect(reverse("bill_order", args=[billing_trx.id]))
    else:
        return HttpResponseRedirect("/")


@passenger_required
def bill_order(request, trx_id, passenger):
    billing_trx = BillingTransaction.by_id(trx_id)
    billing_trx.commit()

    page_specific_class = "transaction_page"
    pending = BillingStatus.PENDING
    processing = BillingStatus.PROCESSING
    approved = BillingStatus.APPROVED
    failed = BillingStatus.FAILED

    return custom_render_to_response("transaction_page.html", locals(), context_instance=RequestContext(request))

def transaction_error(request):
    if request.GET.get("lang") == u"HE":
        request.encoding = "cp1255"

    error_text = request.GET.get("ErrorText")
    return custom_render_to_response("error_page.html", locals(), context_instance=RequestContext(request))

@passenger_required
def get_trx_status(request, passenger):
    trx_id = request.GET.get("trx_id")
    trx = BillingTransaction.by_id(trx_id)

    if trx and trx.passenger == passenger:
        response = {'status': trx.status}
        if trx.status == BillingStatus.FAILED and trx.comments:
            response.update({'error_message': trx.comments})
        return JSONResponse(response)

    return JSONResponse("")

def send_invoices(request, month=None):
    import calendar
    import itertools
    now = default_tz_now()
    month = month or now.month - 1
    start_date = datetime(year=now.year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=now.tzinfo)
    end_date = datetime(year=now.year,
                        month=month,
                        day=calendar.monthrange(now.year, month)[1],
                        hour=23,
                        minute=59,
                        second=59,
                        microsecond=9999,
                        tzinfo=now.tzinfo)

    qs = BillingTransaction.objects.filter(create_date__gte=start_date, create_date__lte=end_date, status=BillingStatus.CHARGED)
    data = sorted(qs, key=lambda trx: trx.passenger_id) # in memory sort since DataStore can only sort on filtering property

    for p, g in itertools.groupby(data, lambda trx: trx.passenger_id):
        logging.info("Creating invoices for %d for month %d" % (p, month))
        create_invoices(sorted(list(g), key=lambda trx: trx.order.create_date))

    return HttpResponse("OK")

def get_csv(request):
    delta = int(request.GET.get("days", 30))
    if request.GET.get("format") == "screen":
        response = HttpResponse()
        writer = csv.writer(response, delimiter=" ", lineterminator="<br>")
    else:
        response = HttpResponse(mimetype='text/csv')
        response['Content-Disposition'] = 'attachment; filename=invoices.csv'
        writer = csv.writer(response)

    cols = ["Ride ID", "Date", "Time", "Station", "Taxi", "Driver Name", "From (area)", "To (area)",
            "Address From 1", "Address To 1", "Passenger 1", "Price 1", "Billing Date 1",
            "Address From 2", "Address To 2", "Passenger 2", "Price 2", "Billing Date 2",
            "Address From 3", "Address To 3", "Passenger 3", "Price 3", "Billing Date 3",
            "Tariff",
            "Base Cost",
            "Number of Stops",
            "Stop Cost",
            "Stops Cost",
            "Total Costs",
            "Revenue",
            ]

    writer.writerow(cols)
    for ride in SharedRide.objects.filter(status__in=[ACCEPTED, COMPLETED], create_date__gt=datetime.now() - timedelta(days=delta)):
        station = ride.station
        price_rules = station.get_ride_price(ride, rules_only=True)
        max_rule = None
        if price_rules:
            max_rule = max(price_rules, key=lambda rule: rule.price)

        base_cost = max_rule.price if max_rule else 0
        stops_cost = station.stop_price * ride.charged_stops
        total_cost = base_cost + stops_cost
        total_price = 0.0
        order_count = 0
        row = [
            ride.id,
            ride.depart_time.date(),
            ride.depart_time.timetz(),
            ride.station.name,
            ride.taxi.number if ride.taxi else "N/A",
            ride.driver.name if ride.driver else "N/A",
            max_rule.city_area_1.name if max_rule else "",
            max_rule.city_area_2.name if max_rule else ""
        ]
        for order in ride.orders.all():
            billing_trx = order.billing_transactions.all()
            if billing_trx:
                billing_trx = billing_trx[0]

            order_count += 1

            total_price += billing_trx.amount if billing_trx else 0
            row += [
                order.from_raw,
                order.to_raw,
                str(order.passenger),
                billing_trx.amount if billing_trx else "NA",
                billing_trx.charge_date_format() if billing_trx else "NA"
            ]

        for i in xrange(3 - order_count):
            row += ["", "", "", "", ""]

        row += [
            max_rule.rule_set.name if max_rule else "",
            base_cost,
            ride.charged_stops,
            station.stop_price,
            stops_cost,
            total_cost,
            total_price - total_cost
        ]

        encoded_row = [unicode(s).encode("utf-8") for s in row]
        writer.writerow(encoded_row)

    return response


def unicode_csv_reader(unicode_csv_data, dialect=csv.excel, **kwargs):
    # csv.py doesn't do Unicode; encode temporarily as UTF-8:
    csv_reader = csv.reader(utf_8_encoder(unicode_csv_data),
                            dialect=dialect, **kwargs)
    for row in csv_reader:
        # decode UTF-8 back to Unicode, cell by cell:
        yield [unicode(cell, 'utf-8') for cell in row]

def utf_8_encoder(unicode_csv_data):
    for line in unicode_csv_data:
        yield line.encode('utf-8')


def credit_guard_page(request):
    page_specific_class = "credit_guard_page"
    return custom_render_to_response("credit_guard_page.jsp", locals(), context_instance=RequestContext(request))