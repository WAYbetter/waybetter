from billing.enums import BillingStatus
from billing.models import BillingTransaction
from billing.signals import billing_failed_signal, billing_approved_signal, billing_charged_signal
from common.decorators import force_lang
from common.models import Counter
from common.urllib_adaptor import urlencode
from common.util import get_text_from_element, get_unique_id, safe_fetch
from ordering.models import CANCELLED, PENDING, APPROVED, CHARGED
from django.conf import settings
from django.http import HttpResponse
from django.template.context import Context
from django.template.loader import get_template
from django.utils.http import urlquote_plus
from django.utils.translation import ugettext as _
from google.appengine.api.urlfetch import fetch
from xml.dom import minidom
import logging
import re
import types

INVOICE_INFO = settings.INVOICE_INFO
BILLING_INFO = settings.BILLING

def do_J5(token, amount, card_expiration, billing_transaction_id):
    billing_transaction = BillingTransaction.by_id(billing_transaction_id)
    billing_transaction.change_status(BillingStatus.PENDING, BillingStatus.PROCESSING)
    lang_code = get_language_code_for_credit_guard(billing_transaction.order.language_code)

    params = {
        'card_id'						: token,
        'card_expiration'				: card_expiration,
        'total'							: amount,
        'billing_transaction_id'		: billing_transaction_id,
        'request_id'					: get_unique_id(),
        'validation'					: "Verify",
        'language'                      : lang_code
        }

    if settings.DEV: # bypass authorization if running on test server
        params.update({"auth_number": "0000000"})

    result = do_credit_guard_trx(params)
    if not result:
        billing_transaction.comments = "CreditGuard transaction failed"
        billing_transaction.change_status(BillingStatus.PROCESSING, BillingStatus.FAILED) #calls save
        billing_failed_signal.send(sender="do_J5", obj=billing_transaction)
        return HttpResponse("OK")

    status_code = get_text_from_element(result, "status")
    auth_number = get_text_from_element(result, "authNumber")
    transaction_id = get_text_from_element(result, "tranId")
    billing_transaction.transaction_id = transaction_id

    if int(status_code):
        message = get_text_from_element(result, "message")
        billing_transaction.comments = message
        billing_transaction.change_status(BillingStatus.PROCESSING, BillingStatus.FAILED) #calls save
        billing_failed_signal.send(sender="do_J5", obj=billing_transaction)
    else:
        billing_transaction.auth_number = auth_number
        billing_transaction.change_status(BillingStatus.PROCESSING, BillingStatus.APPROVED) #calls save
        billing_transaction.order.change_status(old_status=PENDING, new_status=APPROVED)
        billing_approved_signal.send(sender="do_J5", obj=billing_transaction)
        billing_transaction.charge() # setup J4

    return HttpResponse("OK")

def do_J4(token, amount, card_expiration, billing_transaction_id):
    billing_transaction = BillingTransaction.by_id(billing_transaction_id)
    if billing_transaction.status == BillingStatus.CANCELLED or billing_transaction.order.status == CANCELLED:
        return HttpResponse("Cancelled")

    billing_transaction.change_status(BillingStatus.APPROVED, BillingStatus.PROCESSING)

    lang_code = get_language_code_for_credit_guard(billing_transaction.order.language_code)
    params = {
        'card_id'						: token,
        'card_expiration'				: card_expiration,
        'total'							: amount,
        'billing_transaction_id'		: billing_transaction_id,
        'request_id'					: get_unique_id(),
        'validation'					: "AutoComm",
        'auth_number'                   : billing_transaction.auth_number,
        'language'                      : lang_code
        }

    result = do_credit_guard_trx(params)
    if not result:
        billing_transaction.comments = "CreditGuard transaction failed"
        billing_transaction.change_status(BillingStatus.PROCESSING, BillingStatus.FAILED) #calls save
        billing_failed_signal.send(sender="do_J4", obj=billing_transaction)
        return HttpResponse("OK")

    status_code = get_text_from_element(result, "status")
    auth_number = get_text_from_element(result, "authNumber")
    transaction_id = get_text_from_element(result, "tranId")
    billing_transaction.transaction_id = transaction_id

    if int(status_code):
        message = get_text_from_element(result, "message")
        billing_transaction.comments = message
        billing_transaction.change_status(BillingStatus.PROCESSING, BillingStatus.FAILED) #calls save
        billing_failed_signal.send(sender="do_J4", obj=billing_transaction)

    else:
        billing_transaction.auth_number = auth_number
        billing_transaction.change_status(BillingStatus.PROCESSING, BillingStatus.CHARGED) #calls save
        billing_transaction.order.change_status(new_status=CHARGED)
        billing_charged_signal.send(sender="do_J4", obj=billing_transaction)


    return HttpResponse("OK")

def do_credit_guard_trx(params):
    provider_url = BILLING_INFO['url']

    params.update(BILLING_INFO)
    params.update({
        'may_be_duplicate'				: "0",
        'currency'						: "ILS",
        'request_id'					: get_unique_id(),
        'terminal_number'               : BILLING_INFO["terminal_number_no_CVV"]
    })

    c = Context(params)
    t = get_template("credit_guard_transaction.xml")
    rendered_payload = t.render(c)

    logging.info("CREDIT GUARD TRX - payload: %s" % rendered_payload)

    payload = str("user=%s&password=%s&int_in=%s" % (BILLING_INFO["username"], BILLING_INFO["password"], urlquote_plus(rendered_payload)))

    result = safe_fetch(provider_url, method="POST", payload=payload, deadline=50)

    logging.info("CREDIT GUARD TRX - response: %s" % result.content if result else "fetch failed")

    if not result:
        return None
    else:
        result = result.content

    if params["language"] == "Heb":
        result = result.decode("utf-8").encode("hebrew")

    xml = minidom.parseString(result)
    return xml


@force_lang("he")
def send_invoices_passenger(billing_transactions):
    trx = billing_transactions[0]

    if not all([_trx.passenger.id == trx.passenger.id for _trx in billing_transactions]):
        logging.error("all transactions should belong to the same passenger")
        return False

    if not trx.passenger.invoice_id:
        logging.error("failed sending invoices to passenger_id %s: passenger has no invoice_id" % trx.passenger_id)
        return False

    payload = {
        "TransType"						: "IR:CREATE101",
        "Username"						: INVOICE_INFO["invoice_username"],
        "Key"	    					: INVOICE_INFO["invoice_key"],
        "InvoiceSubject"				: "%s %s" %(_("Ride Summary for month"), trx.create_date.strftime("%m/%Y")),
        "InvoiceItemCode"				: "|".join([str(trx.order.id) for trx in billing_transactions]),
        "InvoiceItemDescription"		: "|".join([trx.order.invoice_description for trx in billing_transactions]),
        "InvoiceItemQuantity"			: "|".join(["1" for trx in billing_transactions]),
        "InvoiceItemPrice"				: "|".join([str(trx.amount) for trx in billing_transactions]),
        "MailTo"						: trx.passenger.user.email,
        "CompanyCode"					: trx.passenger.invoice_id,
        "ItemPriceIsWithTax"			: 1,
        }

    url = INVOICE_INFO["invoice_url"]

    payload = dict([(k,v.encode('iso8859_8') if type(v) is types.UnicodeType else v) for (k,v) in payload.items()])
    payload = urlencode(payload)

    result = safe_fetch(url, method="POST", payload=payload, deadline=50, headers={'Content-Type': 'application/x-www-form-urlencoded'})
    response_code = re.findall(r"ResponseCode:(\d+)", result.content)
    if response_code and response_code[0] == "100":
        logging.info("invoices sent to passenger %s" % trx.passenger_id)
        return True
    else:
        logging.error("failed sending invoices to passenger_id %s: response_code=%s" % (trx.passenger_id, response_code))
        return False


def create_invoice_passenger(passenger):
    payload = {
#        "ReplyURL": "ReturnPage.asp",
        "TransType"						: "C:INSERT",
        "Username"						: INVOICE_INFO["invoice_username"],
        "CompanyCode"                   : Counter.get_next(name=INVOICE_INFO["invoice_counter"]),
        "CompanyName"                   : passenger.full_name,
        "CompanyAddress"                : "",
        "CompanyCity"                   : "",
        "CompanyState"                  : "",
        "CompanyZipcode"                : "",
        "CompanyTel1"                   : passenger.phone,
        "CompanyTel2"                   : "",
        "CompanyCell"                   : "",
        "CompanyFax"                    : "",
        "CompanyEmail"                  : passenger.user.email,
        "CompanyWebsite"                : "",
        "CompanyComments"               : "",
        }

    url = INVOICE_INFO["invoice_url"]
    payload = dict([(k,v.encode('iso8859_8') if type(v) is types.UnicodeType else v) for (k,v) in payload.items()])
    payload = urlencode(payload)
    result = safe_fetch(url, method="POST", payload=payload, deadline=50, headers={'Content-Type': 'application/x-www-form-urlencoded'})

    response_code = None
    if result and result.content:
        response_code = re.findall(r"ResponseCode:(\d+)", result.content)
        company_code = re.findall(r"CompanyCode:(\d+)", result.content)
        if response_code and response_code[0] == "100" and company_code:
            passenger.invoice_id = company_code[0]
            passenger.save()
            logging.info("successfully created invoice_id %s for passenger_id %s" % (passenger.invoice_id, passenger.id))

            return passenger.invoice_id

    logging.error("failed creating invoice_id for passenger_id %s: response_code=%s" % (passenger.id, response_code))
    return None


def get_language_code_for_credit_guard(lang_code):
    if lang_code == "en":
        return "Eng"
    else:
        return "Heb"