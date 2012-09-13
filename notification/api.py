import logging
from common.sms_notification import send_sms
from push.backends.UrbanAirshipBackend import UrbanAirshipBackend

PUSH_BACKEND = UrbanAirshipBackend()

def push(passenger, message, data=None):

    logging.info(u"notification: sending push message '%s' to passenger [%s]" % (message, passenger.id))
    res = False
    if passenger.push_token:
        if not PUSH_BACKEND.is_active(passenger.push_token, passenger.mobile_platform):
            logging.warning(u"notification: push sent to inactive device: %s" % passenger.push_token)

        res = PUSH_BACKEND.push(passenger.push_token, passenger.mobile_platform, message, data)
    else:
        logging.warning("notification: send push with no token")
#    elif passenger.phone: # fallback
#        return send_sms(passenger.phone, message)

    logging.info("notification: send push result: %s" % res)
    return res # couldn't send :(

def deregister_push_token(passenger):
    res =  PUSH_BACKEND.deregister(passenger.push_token, passenger.mobile_platform)
    logging.info("notification: deregister push token '%s' for passenger [%s]: %s" % (passenger.push_token, passenger.id, res))
    return res