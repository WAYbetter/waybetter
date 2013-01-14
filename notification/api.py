import logging
from google.appengine.ext import deferred
from common.sms_notification import send_sms, get_sms_status_data, SMSStatus
from common.util import notify_by_email
from django.conf import settings
from push.backends.UrbanAirshipBackend import UrbanAirshipBackend

PUSH_BACKEND = UrbanAirshipBackend()
SMS_DELIVERY_GRACE = 2*60  # seconds

def notify_passenger(passenger, message, data=None, force_sms=False):
    logging.info(u"notification: sending push message '%s' to passenger [%s]" % (message, passenger.id))
    res = False
    if force_sms and passenger.phone:
        sms_id = send_sms(passenger.phone, message)
        if sms_id and not settings.DEV:
            deferred.defer(track_sms, passenger, sms_id, _countdown=SMS_DELIVERY_GRACE)

        return sms_id is not None

    if passenger.push_token:
        if not PUSH_BACKEND.is_active(passenger.push_token, passenger.mobile_platform):
            logging.warning(u"notification: push sent to inactive device: %s" % passenger.push_token)

        res = PUSH_BACKEND.push(passenger.push_token, passenger.mobile_platform, message, data)

    elif passenger.phone: # fallback
        sms_id = send_sms(passenger.phone, message)
        if sms_id and not settings.DEV:
            deferred.defer(track_sms, passenger, sms_id, _countdown=SMS_DELIVERY_GRACE)

        return sms_id is not None

    else:
        logging.warning("notification: send push with no token and no phone")

    logging.info("notification: send push result: %s" % res)
    return res # couldn't send :(


def deregister_push_token(passenger):
    res =  PUSH_BACKEND.deregister(passenger.push_token, passenger.mobile_platform)
    logging.info("notification: deregister push token '%s' for passenger [%s]: %s" % (passenger.push_token, passenger.id, res))
    return res


def track_sms(passenger, sms_id):
    sms_data = get_sms_status_data(sms_id)
    logging.info("track sms_id=%s: %s" % (sms_id, sms_data))

    if sms_data.get('status') != SMSStatus.OK:
        notify_by_email("SMS not received after %s seconds" % SMS_DELIVERY_GRACE, msg=(u"%s\nsms_data: %s" % (passenger, sms_data)))