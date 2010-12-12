import logging
from django.conf import settings
from settings import SMS_PROVIDER_URL, SMS_PROVIDER_USER_NAME, SMS_PROVIDER_PASSWORD, SMS_FROM_PHONE_NUMBER, SMS_FROM_MARKETING_NAME, SMS_FROM_MARKETING_PHONE, SMS_VALIDITY_PERIOD
from django.template.loader import get_template
from django.template.context import Context
from django.utils.http import urlquote_plus
from google.appengine.api.urlfetch import fetch


def send_sms(destination, text, **kwargs):
    """
    sends a text to some user (by given destination phone number) by SMS.
    delegates to a method for specific SMS back-end.
    Returns text response.
    TODO_WB: take back-end function name from settings
    """
    sms_config = settings.SMS
    if kwargs is not None:
        sms_config.update(kwargs) 

    return send_sms_cellact(destination, text, sms_config)

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
    }
    params.update(sms_config)

    c = Context(params)
    t = get_template("cellact_send_sms.xml")
    payload = "XMLString=" + urlquote_plus(t.render(c))
    result = fetch(provider_url, method="POST", payload=payload)
    return result

