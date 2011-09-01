import logging
from xml.dom import minidom
from billing.enums import BillingStatus
from billing.models import BillingTransaction
from billing.signals import billing_failed_signal, billing_approved_signal, billing_charged_signal, BillingSignalType
from common.decorators import receive_signal
from django.http import HttpResponse
from google.appengine.api.urlfetch import fetch
from django.template.loader import get_template
from django.template.context import Context
from django.utils.http import urlquote_plus
from django.conf import settings
from common.util import get_text_from_element, get_unique_id

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

    # TODO: only for dev
    if settings.BILLING["terminal_number"].startswith("096"):
        params.update({
            "auth_number": "0000000"
        })

    result = do_credit_guard_trx(params)
    xml = minidom.parseString(result)
    status_code = get_text_from_element(xml, "status")
    auth_number = get_text_from_element(xml, "authNumber")
    transaction_id = get_text_from_element(xml, "tranId")
    billing_transaction.transaction_id = transaction_id

    if int(status_code):
        message = get_text_from_element(xml, "message")
        billing_transaction.comments = message
        billing_transaction.save()
        billing_transaction.change_status(BillingStatus.PROCESSING, BillingStatus.FAILED)
        billing_failed_signal.send(sender="do_J5", obj=billing_transaction)
    else:
        billing_transaction.auth_number = auth_number
        billing_transaction.save()
        billing_transaction.change_status(BillingStatus.PROCESSING, BillingStatus.APPROVED)
        billing_approved_signal.send(sender="do_J5", obj=billing_transaction)
        billing_transaction.charge() # setup J4

    return HttpResponse("OK")

def do_J4(token, amount, card_expiration, billing_transaction_id):
    billing_transaction = BillingTransaction.by_id(billing_transaction_id)
    if billing_transaction.status == BillingStatus.CANCELLED:
        return HttpResponse("Canceled")
    
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
    xml = minidom.parseString(result)
    status_code = get_text_from_element(xml, "status")
    auth_number = get_text_from_element(xml, "authNumber")
    transaction_id = get_text_from_element(xml, "tranId")
    billing_transaction.transaction_id = transaction_id

    if int(status_code):
        message = get_text_from_element(xml, "message")
        billing_transaction.comments = message
        billing_transaction.save()
        billing_transaction.change_status(BillingStatus.PROCESSING, BillingStatus.FAILED)
        billing_failed_signal.send(sender="do_J4", obj=billing_transaction)

    else:
        billing_transaction.auth_number = auth_number
        billing_transaction.save()
        billing_transaction.change_status(BillingStatus.PROCESSING, BillingStatus.CHARGED)
        billing_charged_signal.send(sender="do_J4", obj=billing_transaction)


    return HttpResponse("OK")

def do_credit_guard_trx(params):
    provider_url = settings.BILLING['url']

    params.update({
        'language'						: "Eng",
        'may_be_duplicate'				: "0",
        'currency'						: "ILS",
        'request_id'					: get_unique_id(),
    })
    params.update(settings.BILLING)
    c = Context(params)
    t = get_template("credit_guard_transaction.xml")
    rendered_payload = t.render(c)

    logging.info("CREDIT GUARD TRX - payload: %s" % rendered_payload)

    payload = str("user=%s&password=%s&int_in=%s" % (settings.BILLING["username"], settings.BILLING["password"], urlquote_plus(rendered_payload)))
    result = fetch(provider_url, method="POST", payload=payload, deadline=50)

    logging.info("CREDIT GUARD TRX - response: %s" % result.content)

    return result.content

@receive_signal(billing_failed_signal, billing_approved_signal, billing_charged_signal)
def test_signal(sender, signal_type, obj, **kwargs):
    logging.info("SIGNAL RECEIVED: %s (%s, %s)" % (BillingSignalType.get_name(signal_type), sender, obj))