import logging
from django.conf import settings
from settings import SMS_PROVIDER_URL, SMS_PROVIDER_USER_NAME, SMS_PROVIDER_PASSWORD, SMS_FROM_PHONE_NUMBER, SMS_FROM_MARKETING_NAME, SMS_FROM_MARKETING_PHONE, SMS_VALIDITY_PERIOD
from pysimplesoap.client import SoapClient


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

    return send_sms_unicell(destination, text, sms_config)


def send_sms_unicell(destination, text, sms_config):
    provider_url = sms_config[SMS_PROVIDER_URL]
    params = (
        (SMS_PROVIDER_USER_NAME, sms_config[SMS_PROVIDER_USER_NAME]),
        (SMS_PROVIDER_PASSWORD, sms_config[SMS_PROVIDER_PASSWORD]),
        (SMS_FROM_PHONE_NUMBER, sms_config[SMS_FROM_PHONE_NUMBER]),
        ('destination',         destination),
        ('text',                text),
        (SMS_VALIDITY_PERIOD, sms_config[SMS_VALIDITY_PERIOD]),
        ('reference',         0),
        ('delayDeliveryMin',  0),
        ('isTest',            0),
        (SMS_FROM_MARKETING_NAME, sms_config[SMS_FROM_MARKETING_NAME]),
        (SMS_FROM_MARKETING_PHONE, sms_config[SMS_FROM_MARKETING_PHONE])
    )

    client = SoapClient(location=provider_url[:-len('?wsdl')], wsdl=provider_url, trace=True)
    result = client.call("sendTextSingle", params)
    logging.debug(result)
    return result

