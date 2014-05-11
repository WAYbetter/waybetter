import logging
from common.enums import MobilePlatform
from notification.push.backends.default import AbstractPushBackend
from notification.push.backends.urbanairship import Airship, AirshipFailure

#APP_KEY = "***REMOVED***" # DEV
#MASTER_SECRET = "***REMOVED***" # DEV

APP_KEY = "***REMOVED***" # PROD
MASTER_SECRET = "***REMOVED***" # PROD

airship = Airship(APP_KEY, MASTER_SECRET)
class UrbanAirshipBackend(AbstractPushBackend):
    def push(self, pushID, platform, message, extra=None):
        if not extra:
            extra = {}

        ios_tokens, android_tokens = None, None

        if platform == MobilePlatform.iOS:
            ios_tokens = [pushID]
            payload = {
                'aps': { 'alert': message, 'sound': 'default' }, }
            payload.update(extra)

        elif platform == MobilePlatform.Android:
            android_tokens = [pushID]
            payload = {
                "android": {
                    "alert": message,
                    "extra": extra
                }
            }
        else:
            logging.error("push error: unknown mobile platform")
            return False

        try:
            airship.push(payload, device_tokens=ios_tokens, APID_tokens=android_tokens)
        except AirshipFailure, e:
            logging.error("push exception: %s" % e.message)
            return False

        return True

    def deregister(self, token, platform):
        logging.info("deregister push token %s.%s" % (MobilePlatform.get_name(platform), token))
        res  = False
        try:
            if platform == MobilePlatform.iOS:
                airship.deregister(token)
                res = True
            elif platform == MobilePlatform.Android:
                airship.deregisterAPID(token)
                res = True

        except AirshipFailure, e:
            logging.error("deregister exception: %s" % e.message)

        return res

    def is_active(self, token, platform):
        res = None
        try:
            if platform == MobilePlatform.iOS:
                res = airship.get_device_token_info(token)
            elif platform == MobilePlatform.Android:
                res = airship.get_APID_token_info(token)
        except AirshipFailure, e:
            logging.error("is_active failed: %s" % e.message)

        return res and res.get("active")

