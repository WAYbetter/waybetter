import logging
from google.appengine.api.urlfetch_errors import DeadlineExceededError
from common.util import split_to_chunks
from django.conf import settings
from settings import SMS_PROVIDER_URL, SMS_CALLBACK_URL
from django.template.loader import get_template
from django.template.context import Context
from django.utils.http import urlquote_plus
from google.appengine.api.urlfetch import fetch

MAX_CHUNK_LENGTH = 126

def send_sms(destination, text, **kwargs):
    """
    sends a text to some user (by given destination phone number) by SMS.
    delegates to a method for specific SMS back-end.
    Returns text response. 
    TODO_WB: take back-end function name from settings
    """

    logging.info(u"Sending SMS to [%s]: '%s'" % (destination, text))

    # don't send SMS to test account
    if destination.endswith(settings.APPLE_TESTER_PHONE_NUMBER):
        logging.info("Skipping SMS for test user")
        return True
 
#    return
    sms_config = settings.SMS
    if kwargs is not None:
        sms_config.update(kwargs)

    ok = True

    for chunk in list(split_to_chunks(text, MAX_CHUNK_LENGTH)):
        result = send_sms_cellact(destination, chunk, sms_config)

        if not result:
            logging.error("error sending sms")
            ok = False

    return ok

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

        if result.content.find("<RESULTCODE>0</RESULTCODE>") == -1:
            logging.error("error sending sms: %s" % result.content)
            return None
        else:
            return result

    except DeadlineExceededError:
        logging.warn("SMS sending failed due to DeadlineExceededError, retrying")
        send_sms_cellact(destination, text, sms_config)