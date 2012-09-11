from common.sms_notification import send_sms
from push.backends.UrbanAirshipBackend import UrbanAirshipBackend

PUSH_BACKEND = UrbanAirshipBackend()

def push(passenger, message, data=None):
    if passenger.push_token:
        return PUSH_BACKEND.push(passenger.push_token, message, data)
#    elif passenger.phone: # fallback
#        return send_sms(passenger.phone, message)

    return False # couldn't send :(

