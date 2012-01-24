# This Python file uses the following encoding: utf-8
from django.db import models
from django.template.loader import get_template
from django.template.context import  Context
from django.utils.translation import ugettext
from google.appengine.api import channel
from django.db.models.loading import get_model
from django.contrib.auth.models import User
from django.utils import simplejson
from ordering.models import Passenger
from common.util import log_event, EventType, get_channel_key, notify_by_email, send_mail_as_noreply
from common.sms_notification import send_sms
from oauth2.models import FacebookSession
import logging

def send_msg_to_passenger(passenger, msg):
    if not msg:
        logging.error("skipping msg to passenger [%d]: empty msg" % passenger.id)
    elif passenger.business:
        send_channel_msg_to_passenger(passenger, msg)
    else:
        phone = passenger.international_phone()
        if phone:
            logging.info("sending message passenger [%d]: %s" % (passenger.id, msg))
            send_sms(phone, msg)
        else:
            logging.error("Passenger [%d] missing phone - skipping message: %s" % (passenger.id, msg))

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
        except KeyError:
            logging.error(
                "KeyError: Failed sending channel message to passenger[%d]: %s" % (passenger.id, msg))



def create_user(username, password="", email="", first_name="", last_name="", save=True):
    user = User.objects.create_user(username, email, password)
    user.first_name = first_name
    user.last_name = last_name

    if email and not user.first_name:
        user.first_name = email.split("@")[0]

    if save:
        user.save()

    # welcome the new user
    if user.email:
        t = get_template("welcome_email.html")
        send_mail_as_noreply(user.email, u"WAYbetter - %s" % ugettext("Shared Taxi Rides"), html=t.render(Context()))

    logging.info("welcome new user: %s" % user)
    return user


def create_passenger(user, country, phone, save=True):
    passenger = Passenger()
    passenger.user = user
    passenger.country = country
    passenger.phone = phone
    passenger.phone_verified = True

    if save:
        passenger.save()
        log_event(EventType.PASSENGER_REGISTERED, passenger=passenger)

    logging.info("welcome new passenger %s" % passenger)
    return passenger

def safe_delete_user(user, remove_from_db=False):
    # delete facebook session
    for fb_session in FacebookSession.objects.filter(user=user):
        fb_session.delete()
    logging.info("deleted facebook sessions")

    # delete social account associated with the user
    social_model_names = ["AuthMeta", "FacebookUserProfile", "OpenidProfile", "TwitterUserProfile",
                          "LinkedInUserProfile"]
    for model_name in social_model_names:
        model = get_model('socialauth', model_name)
        try:
            model.objects.get(user=user).delete()
        except model.DoesNotExist:
            pass

#    by default don't use user.delete(), mark user as inactive instead
    user.is_active = False
    user.save()
    logging.info("safe delete user [%d, %s]: marked as inactive" % (user.id, user.username))

    if remove_from_db:
        try:
            passenger = user.passenger
            passenger.user = None
            passenger.save()
        except Passenger.DoesNotExist:
            pass

        user.delete()
        logging.warn("delete user [%d, %s]: " % (user.id, user.username))


# notify us when users/passengers are deleted
from testing.selenium_helper import SELENIUM_USER_NAMES, SELENIUM_EMAIL
def post_delete_user(sender, instance, **kwargs):
    if instance.email == SELENIUM_EMAIL or instance.username in SELENIUM_USER_NAMES:
        pass
    else:
        notify_by_email("user deleted [%d, %s]" % (instance.id, instance.username))

def post_delete_passenger(sender, instance, **kwargs):
    if instance.user and (instance.user.email == SELENIUM_EMAIL or instance.user.username in SELENIUM_USER_NAMES):
        pass
    else:
        notify_by_email("passenger deleted [%d, %s]" % (instance.id, unicode(instance)))

models.signals.post_delete.connect(post_delete_user, sender=User)
models.signals.post_delete.connect(post_delete_passenger, sender=Passenger)
