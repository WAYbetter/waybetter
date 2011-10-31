from billing.enums import BillingStatus
from billing.models import BillingTransaction
from billing.signals import billing_failed_signal, billing_approved_signal, billing_charged_signal
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

def do_J5(token, amount, card_expiration, billing_transaction_id):
    billing_transaction = BillingTransaction.by_id(billing_transaction_id)
    billing_transaction.change_status(BillingStatus.PENDING, BillingStatus.PROCESSING)

    params = {
        'card_id'						: token,
        'card_expiration'				: card_expiration,
        'total'							: amount,
        'billing_transaction_id'		: billing_transaction_id,
        'request_id'					: get_unique_id(),
        'validation'					: "Verify",
        }

    # only for test terminals (who start with 096)
    if settings.BILLING["terminal_number"].startswith("096"):
        params.update({
            "auth_number": "0000000"
        })

    result = do_credit_guard_trx(params)
    if not result:
        billing_transaction.comments = "CreditGuard transaction failed"
        billing_transaction.change_status(BillingStatus.PROCESSING, BillingStatus.FAILED) #calls save
        billing_failed_signal.send(sender="do_J5", obj=billing_transaction)
        return HttpResponse("OK")

    xml = minidom.parseString(result)
    status_code = get_text_from_element(xml, "status")
    auth_number = get_text_from_element(xml, "authNumber")
    transaction_id = get_text_from_element(xml, "tranId")
    billing_transaction.transaction_id = transaction_id

    #TODO_WB: remove once J5 is approved
    status_code = 0
    
    if int(status_code):
        message = get_text_from_element(xml, "message")
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

    params = {
        'card_id'						: token,
        'card_expiration'				: card_expiration,
        'total'							: amount,
        'billing_transaction_id'		: billing_transaction_id,
        'request_id'					: get_unique_id(),
        'validation'					: "AutoComm",
        'auth_number'                   : billing_transaction.auth_number
        }

    result = do_credit_guard_trx(params)
    if not result:
        billing_transaction.comments = "CreditGuard transaction failed"
        billing_transaction.change_status(BillingStatus.PROCESSING, BillingStatus.FAILED) #calls save
        billing_failed_signal.send(sender="do_J4", obj=billing_transaction)
        return HttpResponse("OK")

    xml = minidom.parseString(result)
    status_code = get_text_from_element(xml, "status")
    auth_number = get_text_from_element(xml, "authNumber")
    transaction_id = get_text_from_element(xml, "tranId")
    billing_transaction.transaction_id = transaction_id

    if int(status_code):
        message = get_text_from_element(xml, "message")
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
    provider_url = settings.BILLING['url']

    params.update(settings.BILLING)
    params.update({
        'language'						: "Eng", #TODO_WB: pass the correct lang code here
        'may_be_duplicate'				: "0",
        'currency'						: "ILS",
        'request_id'					: get_unique_id(),
        'terminal_number'               : settings.BILLING["terminal_number_no_CVV"]
    })

    c = Context(params)
    t = get_template("credit_guard_transaction.xml")
    rendered_payload = t.render(c)

    logging.info("CREDIT GUARD TRX - payload: %s" % rendered_payload)

    payload = str("user=%s&password=%s&int_in=%s" % (settings.BILLING["username"], settings.BILLING["password"], urlquote_plus(rendered_payload)))

    result = safe_fetch(provider_url, method="POST", payload=payload, deadline=50)

    logging.info("CREDIT GUARD TRX - response: %s" % result.content if result else "fetch failed")

    return result.content if result else None

def create_invoices(billing_transactions):
    trx = billing_transactions[0]
    if not trx.passenger.invoice_id:
        create_invoice_passenger(trx.passenger)

    payload = {
        "TransType"						: "IR:CREATE101",
        "Username"						: settings.BILLING["invoice_username"],
        "InvoiceSubject"				: _("Ride Summary"),
        "InvoiceItemCode"				: "|".join([str(trx.id) for trx in billing_transactions]),
        "InvoiceItemDescription"		: "|".join([trx.order.invoice_description for trx in billing_transactions]),
        "InvoiceItemQuantity"			: "|".join(["1" for trx in billing_transactions]),
        "InvoiceItemPrice"				: "|".join([str(trx.amount) for trx in billing_transactions]),
        "MailTo"						: trx.passenger.user.email,
        "CompanyCode"					: trx.passenger.invoice_id,
        "ItemPriceIsWithTax"			: 1,
        }

    url = settings.BILLING["invoice_url"]

    payload = dict([(k,v.encode('iso8859_8') if type(v) is types.UnicodeType else v) for (k,v) in payload.items()])
    payload = urlencode(payload)

    result = fetch(url, method="POST", payload=payload, deadline=50, headers={'Content-Type': 'application/x-www-form-urlencoded'})
    response_code = re.findall(r"ResponseCode:(\d+)", result.content)
    if not response_code or not response_code[0] == "100":
        logging.error("Could not send invoices: %s" % response_code)
        raise RuntimeError("Could not send invoices: %s" % response_code)


    return result

def create_invoice_passenger(passenger):
    payload = {
#        "ReplyURL": "ReturnPage.asp",
        "TransType"						: "C:INSERT",
        "Username"						: settings.BILLING["invoice_username"],
        "CompanyCode"                   : Counter.get_next(name=settings.BILLING["invoice_counter"]),
        "CompanyName"                   : passenger.name,
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

    url = settings.BILLING["invoice_url"]
    payload = urlencode(payload)
    result = fetch(url, method="POST", payload=payload, deadline=50, headers={'Content-Type': 'application/x-www-form-urlencoded'})

    response_code = re.findall(r"ResponseCode:(\d+)", result.content)
    company_code = re.findall(r"CompanyCode:(\d+)", result.content)
    if not response_code or not response_code[0] == "100" or not company_code:
        logging.error("Could not create invoice passenger: %s" % response_code)
        raise RuntimeError("Could not create invoice passenger: %s" % response_code)

    passenger.invoice_id = company_code[0]
    passenger.save()

    return result


