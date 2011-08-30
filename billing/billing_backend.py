import logging
from xml.dom import minidom
from billing.enums import BillingStatus
from billing.models import BillingTransaction, InvalidOperationError
from django.http import HttpResponse
from google.appengine.api.urlfetch import fetch
from django.template.loader import get_template
from django.template.context import Context
from django.utils.http import urlquote_plus
from django.conf import settings
from common.util import get_text_from_element, get_unique_id

def do_J4_2(token, amount, card_expiration, billing_transaction_id):
    billing_transaction = BillingTransaction.by_id(billing_transaction_id)
    billing_transaction._change_attr_in_transaction("status", BillingStatus.APPROVED, BillingStatus.PROCESSING, safe=False)

    provider_url = settings.BILLING['url']
    auth_number = get_auth_number(token, amount, card_expiration, billing_transaction_id)
    logging.info("AUTH: %s" % auth_number)
    billing_transaction = BillingTransaction.by_id(billing_transaction_id)
#    if not auth_number:
#        # update billing_transaction_id
#        return HttpResponse("OK")

    params = {
        'language': "Eng",
        'may_be_duplicate': "0",
        'card_id': token,
        'card_expiration': card_expiration,
        'currency': "ILS",
        'total': amount,
        'billing_transaction_id': billing_transaction.id,
        'auth_number': auth_number or '0000000'
    }
    params.update(settings.BILLING)
    c = Context(params)
    t = get_template("credit_guard_transaction.xml")
    rendered_payload = t.render(c)
    logging.info("billing payload: %s" % rendered_payload)
    payload = str("user=%s&password=%s&int_in=%s" %(settings.BILLING["username"], settings.BILLING["password"], urlquote_plus(rendered_payload)))
    result = fetch(provider_url, method="POST", payload=payload)

    xml = minidom.parseString(result.content)
    status_code = get_text_from_element(xml, "result")
    message = get_text_from_element(xml, "message")
    transaction_id = get_text_from_element(xml, "tranId")
    billing_transaction.transaction_id = transaction_id
    billing_transaction.save()

    if int(status_code):
        billing_transaction.comments = message
        billing_transaction._change_attr_in_transaction("status", BillingStatus.PROCESSING, BillingStatus.FAILED, safe=False)
    else:
        billing_transaction._change_attr_in_transaction("status", BillingStatus.PROCESSING, BillingStatus.APPROVED, safe=False)


    logging.info((status_code, message))

    return HttpResponse("OK")

def do_J5(token, amount, card_expiration, billing_transaction_id):
    billing_transaction = BillingTransaction.by_id(billing_transaction_id)
    billing_transaction._change_attr_in_transaction("status", BillingStatus.PENDING, BillingStatus.PROCESSING, safe=False)

    provider_url = settings.BILLING['url']
    params = {
        'language'						: "Eng",
        'may_be_duplicate'				: "0",
        'card_id'						: token,
        'card_expiration'				: card_expiration,
        'currency'						: "ILS",
        'total'							: amount,
        'billing_transaction_id'		: billing_transaction_id,
        'request_id'					: get_unique_id(),
        'validation'					: "Verify",
        'auth_number'                   : "0000000"
        }
    params.update(settings.BILLING)
    c = Context(params)
    t = get_template("credit_guard_transaction.xml")
    rendered_payload = t.render(c)
    logging.info("AUTH payload: %s" % rendered_payload)
    payload = str("user=%s&password=%s&int_in=%s" % (settings.BILLING["username"], settings.BILLING["password"], urlquote_plus(rendered_payload)))
    result = fetch(provider_url, method="POST", payload=payload, deadline=50)
    logging.info("AUTH response: %s" % result.content)

    xml = minidom.parseString(result.content)
    status_code = get_text_from_element(xml, "status")
    auth_number = get_text_from_element(xml, "authNumber")
    transaction_id = get_text_from_element(xml, "tranId")
    billing_transaction.transaction_id = transaction_id

    if int(status_code):
        message = get_text_from_element(xml, "message")
        billing_transaction.comments = message
        billing_transaction.save()
        billing_transaction._change_attr_in_transaction("status", BillingStatus.PROCESSING, BillingStatus.FAILED, safe=False)
    else:
        billing_transaction.auth_number = auth_number
        billing_transaction.save()
        billing_transaction._change_attr_in_transaction("status", BillingStatus.PROCESSING, BillingStatus.APPROVED, safe=False)
        billing_transaction.charge() # setup J4

    return HttpResponse("OK")

def do_J4(token, amount, card_expiration, billing_transaction_id):
    billing_transaction = BillingTransaction.by_id(billing_transaction_id)
    if billing_transaction.status == BillingStatus.CANCELLED:
        return HttpResponse("Canceled")
    
    billing_transaction._change_attr_in_transaction("status", BillingStatus.APPROVED, BillingStatus.PROCESSING, safe=False)

    provider_url = settings.BILLING['url']
    params = {
        'language'						: "Eng",
        'may_be_duplicate'				: "0",
        'card_id'						: token,
        'card_expiration'				: card_expiration,
        'currency'						: "ILS",
        'total'							: amount,
        'billing_transaction_id'		: billing_transaction_id,
        'request_id'					: get_unique_id(),
        'validation'					: "AutoComm",
        'auth_number'                   : billing_transaction.auth_number
        }
    params.update(settings.BILLING)
    c = Context(params)
    t = get_template("credit_guard_transaction.xml")
    rendered_payload = t.render(c)
    logging.info("AUTH payload: %s" % rendered_payload)
    payload = str("user=%s&password=%s&int_in=%s" % (settings.BILLING["username"], settings.BILLING["password"], urlquote_plus(rendered_payload)))
    result = fetch(provider_url, method="POST", payload=payload, deadline=50)
    logging.info("AUTH response: %s" % result.content)

    xml = minidom.parseString(result.content)
    status_code = get_text_from_element(xml, "status")
    auth_number = get_text_from_element(xml, "authNumber")
    transaction_id = get_text_from_element(xml, "tranId")
    billing_transaction.transaction_id = transaction_id

    if int(status_code):
        message = get_text_from_element(xml, "message")
        billing_transaction.comments = message
        billing_transaction.save()
        billing_transaction._change_attr_in_transaction("status", BillingStatus.PROCESSING, BillingStatus.FAILED, safe=False)
    else:
        billing_transaction.auth_number = auth_number
        billing_transaction.save()
        billing_transaction._change_attr_in_transaction("status", BillingStatus.PROCESSING, BillingStatus.COMPLETE, safe=False)

    return HttpResponse("OK")