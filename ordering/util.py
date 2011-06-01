from google.appengine.api import channel
from django.db.models.loading import get_model
from django.contrib.auth.models import User
from django.utils import simplejson
from ordering.models import Passenger
from common.util import log_event, EventType, get_channel_key
from common.sms_notification import send_sms
import logging

def send_msg_to_passenger(passenger, msg):
    if passenger.business:
        send_channel_msg_to_passenger(passenger, msg)
    else:
        send_sms(passenger.international_phone(), msg)

def send_channel_msg_to_passenger(passenger, msg):
    msg = simplejson.dumps(msg)

    for session_key in passenger.session_keys:
        channel_key = get_channel_key(passenger, key_data=session_key)
        try:
            channel.send_message(channel_key, msg)
        except channel.InvalidChannelClientIdError:
            logging.error(
                "InvalidChannelClientIdError: Failed sending channel message to passenger[%d]: %s" % (passenger.id, msg))
        except channel.InvalidMessageError:
            logging.error(
                "InvalidMessageError: Failed sending channel message to passenger[%d]: %s" % (passenger.id, msg))


def create_user(username, password, email, first_name=None):
    user = User()
    user.username = username
    user.set_password(password)
    user.email = email
    if email and not first_name:
        first_name = email.split("@")[0]
    user.first_name = first_name
    user.is_active = True
    user.save()

    return user


def safe_delete_user(user):
    # delete social account associated with the user
    social_model_names = ["AuthMeta", "FacebookUserProfile", "OpenidProfile", "TwitterUserProfile",
                          "LinkedInUserProfile"]
    for model_name in social_model_names:
        model = get_model('socialauth', model_name)
        try:
            model.objects.get(user=user).delete()
        except model.DoesNotExist:
            pass

    user.delete()


def create_passenger(user, country, phone):
    passenger = Passenger()
    passenger.user = user
    passenger.country = country
    passenger.phone = phone
    passenger.phone_verified = True
    passenger.save()
    log_event(EventType.PASSENGER_REGISTERED, passenger=passenger)
    return passenger