from common.util import split_to_chunks, get_text_from_element, Enum
from django.conf import settings
from django.http import HttpResponse
from django.template.loader import get_template
from django.template.context import Context
from django.utils.http import urlquote_plus
from google.appengine.api.urlfetch_errors import DeadlineExceededError
from google.appengine.api.urlfetch import fetch
from google.appengine.api import memcache
from settings import SMS_PROVIDER_URL, SMS_CALLBACK_URL
from urllib2 import unquote
import logging
import xml


MAX_CHUNK_LENGTH = 126

SMS_STATUS_MEMCACHE_NS = "SMS_STATUS_MEMCACHE_NS"

class SMSStatus(Enum):
    PENDING = 0
    OK = 1
    NOK = 2


def get_sms_status_data(sms_id):
    """
    @param sms_id:
    @return: a dict of the form:
        {
            'status': SMSStatus
            'content': the content of the message sent
            'destination': the destination of the message

            # the following keys exists only if an update was received by SMS provider
            'raw_status': the raw_status as sent by the SMS provider
            'reason': the reason as sent by the SMS provider
        }
    """
    if not sms_id:
        return {}

    else:
        data =  memcache.get(sms_id, namespace=SMS_STATUS_MEMCACHE_NS)
        return data


def send_sms(destination, text, **kwargs):
    """
    sends a text to some user (by given destination phone number) by SMS.
    delegates to a method for specific SMS back-end.
    Returns text response. 
    TODO_WB: take back-end function name from settings
    """

    if settings.DEV:
        logging.info("DEV environment: skipping SMS to %s" % destination)
        return True

    logging.info(u"Sending SMS to [%s]: '%s'" % (destination, text))

    # don't send SMS to test account
    if destination.endswith(settings.APPLE_TESTER_PHONE_NUMBER):
        logging.info("Skipping SMS for test user")
        return True
 
    sms_config = settings.SMS
    if kwargs is not None:
        sms_config.update(kwargs)

    # in case of a long message the sms_id of the last chuck is used
    sms_id = None

    for chunk in list(split_to_chunks(text, MAX_CHUNK_LENGTH)):
        sms_id = send_sms_cellact(destination, chunk, sms_config)

    if sms_id:
        memcache.set(sms_id, {'status': SMSStatus.PENDING, 'content': text, 'destination': destination}, namespace=SMS_STATUS_MEMCACHE_NS)
    else:
        logging.error("error sending sms")

    return sms_id

def send_sms_unicell(destination, text, sms_config):
    provider_url = sms_config[SMS_PROVIDER_URL]
    params = {
        'destination':         destination,
        'text':                text,
        'is_test':             "false",
    }
    params.update(sms_config)

    c = Context(params)
    t = get_template("unicell_send_sms.xml")
    payload = t.render(c)
    result = fetch(provider_url, method="POST", payload=payload)
    logging.debug(result)
    logging.debug(result.content)
    return result

def send_sms_cellact(destination, text, sms_config):
    provider_url = sms_config[SMS_PROVIDER_URL]
    params = {
        'destination':         destination,
        'text':                text,
        'is_test':             "false",
        'confirmation_url':    sms_config[SMS_CALLBACK_URL]
    }
    params.update(sms_config)

    c = Context(params)
    t = get_template("cellact_send_sms.xml")
    rendered_payload = t.render(c)
    logging.info("sms payload: %s" % rendered_payload)
    payload = str("XMLString=" + urlquote_plus(rendered_payload))

    try:
        result = fetch(provider_url, method="POST", payload=payload, deadline=50)
        respone_content = unquote(result.content)
        logging.info("cellact response %s" % respone_content)

        if respone_content.find("<RESULTCODE>0</RESULTCODE>") == -1:
            logging.error("error sending sms: %s" % result.content)
            return None
        else:
            dom = xml.dom.minidom.parseString(respone_content)
            sms_id = get_text_from_element(dom, "BLMJ")
            logging.info("cellact send success sms_id=%s" % sms_id)
            return sms_id

    except DeadlineExceededError:
        logging.warn("SMS sending failed due to DeadlineExceededError, retrying")
        return send_sms_cellact(destination, text, sms_config)


def confirm_sms(request):
    confirm_sms_cellact(request)
    return HttpResponse("OK")


def confirm_sms_cellact(request):
    confirmation_xml = unquote(request.GET.get("CONFIRMATION"))
    logging.info(confirmation_xml)

    dom = xml.dom.minidom.parseString(confirmation_xml)
    sms_id = get_text_from_element(dom, "BLMJ")
    raw_status = get_text_from_element(dom, "EVT")
    reason = get_text_from_element(dom, "REASON")

    status = SMSStatus.NOK
    if raw_status == "mt_del":  # delivered
        status = SMSStatus.OK

    sms_data = memcache.get(sms_id, namespace=SMS_STATUS_MEMCACHE_NS) or {}
    sms_data.update({'status': status, 'raw_status': raw_status, 'reason': reason})
    memcache.set(sms_id, sms_data, namespace=SMS_STATUS_MEMCACHE_NS)