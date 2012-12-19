# Create your views here.
from datetime import  date, datetime, timedelta
import logging
import csv
import calendar
import itertools
import pickle
from google.appengine.api.taskqueue import taskqueue
from billing import billing_backend
from billing.billing_backend import send_invoices_passenger, create_invoice_passenger, get_custom_message
from billing.enums import BillingStatus, BillingAction
from common.tz_support import default_tz_now, default_tz_time_max, default_tz_time_min
from common.util import custom_render_to_response, notify_by_email, Enum, ga_track_event
from django.core.urlresolvers import reverse
from django.utils import translation
from django.views.decorators.csrf import csrf_exempt
from billing.models import BillingForm, InvalidOperationError, BillingTransaction, BillingInfo
from common.decorators import require_parameters, internal_task_on_queue, catch_view_exceptions
from django.http import HttpResponse, HttpResponseRedirect
from django.template.context import RequestContext
from djangotoolbox.http import JSONResponse
from ordering.decorators import passenger_required_no_redirect, passenger_required
from ordering.models import    CURRENT_ORDER_KEY, CURRENT_BOOKING_DATA_KEY

class InvoiceActions(Enum):
    CREATE_ID	= 0
    SEND		= 1

def bill_passenger(request):
    form = BillingForm(data=request.POST)
    if form.is_valid():
        billing_tx = form.save()
        billing_tx.commit()

    return HttpResponse("OK")


@csrf_exempt
@catch_view_exceptions
@internal_task_on_queue("orders")
@require_parameters(method="POST",
                    required_params=("token", "card_expiration", "billing_transaction_id", "action"))
def billing_task(request, token, card_expiration, billing_transaction_id, action):
    logging.info("billing task: transaction_id=%s" % billing_transaction_id)
    action = int(action)

    # update billing transaction amount
    billing_transaction = BillingTransaction.by_id(billing_transaction_id)
    billing_transaction.amount = billing_transaction.order.get_billing_amount()
    if billing_transaction.dirty_fields:
        logging.info("billing_task [%s]: updating billing transaction amount: %s --> %s" % (BillingAction.get_name(action), billing_transaction.dirty_fields.get("amount"), billing_transaction.amount))
        billing_transaction.save()

    callback_args = request.POST.get("callback_args")
    if callback_args:
        callback_args = pickle.loads(callback_args.encode("utf-8"))

    amount = billing_transaction.amount_in_cents

    if action == BillingAction.COMMIT:
        return billing_backend.do_J5(token, amount, card_expiration, billing_transaction, callback_args=callback_args)
    elif action == BillingAction.CHARGE:
        return billing_backend.do_J4(token, amount, card_expiration, billing_transaction)
    else:
        raise InvalidOperationError("Unknown action for billing: %s" % action)


@passenger_required_no_redirect
def transaction_ok(request, passenger):
    from analytics.models import BIEvent, BIEventType

    #TODO: handle errors
    #TODO: makesure referrer is creditguard
    ga_track_event(request, "registration", "credit_card_validation", "approved")
    date_string = request.GET.get("cardExp")
    exp_date = date(year=int(date_string[2:]) + 2000, month=int(date_string[:2]), day=1)
    kwargs = {
        "passenger"			: passenger,
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

    BIEvent.log(BIEventType.BILLING_INFO_COMPLETE, passenger=passenger, request=request)

    if request.session.get(CURRENT_BOOKING_DATA_KEY) and not request.mobile:  # continue booking process, mobile continues by closing child browser
        logging.info("redirect /booking/continued after billing registration: %s" % passenger)
        return HttpResponseRedirect(reverse("booking_continued"))
    else:
        return HttpResponseRedirect(reverse("wb_home"))


@passenger_required
def bill_order(request, trx_id, passenger):
    billing_trx = BillingTransaction.by_id(trx_id)

    request.session[CURRENT_ORDER_KEY] = None

    page_specific_class = "transaction_page"
    pending = BillingStatus.PENDING
    processing = BillingStatus.PROCESSING
    approved = BillingStatus.APPROVED
    failed = BillingStatus.FAILED

    return custom_render_to_response("transaction_page.html", locals(), context_instance=RequestContext(request))

def transaction_error(request):
    if request.GET.get("lang") == u"HE":
        request.encoding = "cp1255"

    page_specific_class = "error-page"
    error_code = request.GET.get("ErrorCode")
    error_text = get_custom_message(error_code, request.GET.get("ErrorText"))

    ga_track_event(request, "registration", "credit_card_validation", "not_approved", int(error_code))

    return custom_render_to_response("error_page.html", locals(), context_instance=RequestContext(request))

@passenger_required_no_redirect
def get_trx_status(request, passenger):
    trx_id = request.GET.get("trx_id")
    trx = BillingTransaction.by_id(trx_id)

    if trx and trx.passenger == passenger:
        response = {'status': trx.status}
        if trx.status == BillingStatus.FAILED:
            msg = get_custom_message(trx.provider_status, trx.comments)
            if msg:
                response.update({'error_message': msg})
        return JSONResponse(response)

    return JSONResponse({'status': BillingStatus.FAILED})

def create_invoice_ids(request):
    try:
        task = taskqueue.Task(url=reverse(invoices_task), params={"action": InvoiceActions.CREATE_ID})
        q = taskqueue.Queue("billing")
        q.add(task)
        return HttpResponse("Task Added")
    except Exception, e:
        return HttpResponse("FAILED: %s" % e.message)


def send_invoices(request):
    try:
        task = taskqueue.Task(url=reverse(invoices_task), params={"action": InvoiceActions.SEND})
        q = taskqueue.Queue("billing")
        q.add(task)
        return HttpResponse("Task Added")
    except Exception, e:
        return HttpResponse("FAILED: %s" % e.message)


@csrf_exempt
@catch_view_exceptions
@internal_task_on_queue("billing")
def invoices_task(request):
    action = int(request.POST.get("action", -1))

    now = default_tz_now()
    last_month_date = (now - timedelta(days=now.day))
    month = last_month_date.month
    year = last_month_date.year

    start_date = datetime.combine(date(year=year, month=month, day=1), default_tz_time_min())
    end_date = datetime.combine(date(year=year, month=month, day=calendar.monthrange(year, month)[1]), default_tz_time_max())

    trx_qs = BillingTransaction.objects.filter(debug=False, invoice_sent=False, status=BillingStatus.CHARGED, charge_date__gte=start_date, charge_date__lte=end_date)

    if action == InvoiceActions.CREATE_ID:
        logging.info("Creating invoice ids: %s - %s" % (start_date, end_date))
        failed = do_create_invoice_ids(trx_qs)
    elif action == InvoiceActions.SEND:
        logging.info("Sending invoices: %s - %s" % (start_date, end_date))
        failed = do_send_invoices(trx_qs)
    else:
        raise RuntimeError("NOT A VALID INVOICE ACTION")

    action_name = InvoiceActions.get_name(action)
    if failed:
        notify_by_email("Error %s invoices for month %s/%s" % (action_name, month, year), "failed with following passenger ids %s" % failed)
    else:
        notify_by_email("Success %s invoices for month %s/%s" % (action_name, month, year))

    return HttpResponse("OK")


def do_create_invoice_ids(trx_qs):
    failed_ids = []
    passengers = set([trx.passenger for trx in trx_qs])
    for passenger in passengers:
        invoice_id = passenger.invoice_id
        if invoice_id:
            logging.info("skipping passenger_id %s: already has invoice_id=%s" % (passenger.id, invoice_id))
        else:
            try:
                invoice_id = create_invoice_passenger(passenger)
                logging.info("successfully created invoice_id=%s for passenger_id %s" % (invoice_id, passenger.id))
            except Exception, e:
                logging.error("caught exception when creating invoices id for passenger_id %s: %s" % (passenger.id, e.message))

            if not invoice_id:
                failed_ids.append(passenger.id)

    return failed_ids

def do_send_invoices(trx_qs):
    failed_ids = []
    
    data = sorted(trx_qs, key=lambda trx: trx.passenger_id) # in memory sort since DataStore can only sort on filtering property

    for p_id, g in itertools.groupby(data, lambda trx: trx.passenger_id):
        ok = False
        try:
            ok = send_invoices_passenger(sorted(list(g), key=lambda trx: trx.order.create_date))
        except Exception, e:
            logging.error("caught exception when sending invoices for passenger_id %s: %s" % (p_id, e.message))

        if not ok:
            failed_ids.append(p_id)

    return failed_ids


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
    current_lang = translation.get_language()
    translation.activate("en") # make sure we are in english

    page_specific_class = "credit_guard_page"
    response = custom_render_to_response("credit_guard_page.jsp", locals(), context_instance=RequestContext(request))

    translation.activate(current_lang)
    return response