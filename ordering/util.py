# This Python file uses the following encoding: utf-8
import re
from django.db import models
from django.template.loader import get_template
from django.template.context import  Context
from django.utils.translation import ugettext
from google.appengine.api import channel
from django.db.models.loading import get_model
from django.contrib.auth.models import User
from django.utils import simplejson
from ordering.models import Passenger, SharedRide, RidePoint, StopType, APPROVED, ACCEPTED, PickMeAppRide
from ordering.errors import UpdateUserError
from common.util import log_event, EventType, get_channel_key, send_mail_as_noreply
from common.sms_notification import send_sms
from oauth2.models import FacebookSession
import logging
import datetime

def create_single_order_ride(order):
    from sharing.signals import ride_created_signal

    if order.status != APPROVED:
        logging.error("denied creating ride for unapproved order [%s]" % order.id)
        return None

    ride = SharedRide()
    ride.debug = order.debug
    ride.depart_time = order.depart_time
    ride.arrive_time = order.arrive_time
    ride.save()

    pickup = RidePoint()
    pickup.ride = ride
    pickup.stop_time = order.depart_time
    pickup.type = StopType.PICKUP
    pickup.address = order.from_raw
    pickup.lat = order.from_lat
    pickup.lon = order.from_lon
    pickup.save()

    dropoff = RidePoint()
    dropoff.ride = ride
    dropoff.stop_time = order.arrive_time
    dropoff.type = StopType.DROPOFF
    dropoff.address = order.to_raw or order.from_raw
    dropoff.lat = order.to_lat or order.from_lat
    dropoff.lon = order.to_lon or order.from_lon
    dropoff.save()

    order.ride = ride
    order.pickup_point = pickup
    order.dropoff_point = dropoff
    order.save()

    logging.info("created single order ride: order[%s] -> ride[%s]" % (order.id, ride.id))
    ride_created_signal.send(sender='create_single_order_ride', obj=ride)
    return ride


def create_pickmeapp_ride(order):
    from sharing.signals import ride_created_signal

    if order.status != ACCEPTED:
        logging.error("denied creating pickmeapp ride for unaccepted order [%s]" % order.id)
        return None

    ride = PickMeAppRide()
    ride.order = order
    ride.debug = order.debug
    ride.depart_time = order.assignments.get(status=ACCEPTED).create_date + datetime.timedelta(minutes=order.pickup_time)
    ride.arrive_time = ride.depart_time + datetime.timedelta(minutes=10) # we don't know the arrive time for pickmeapp rides
    ride.station = order.station
    ride.dn_fleet_manager_id = order.station.fleet_manager_id
    ride.save()

    logging.info("created pickmeapp ride: order[%s] -> ride[%s]" % (order.id, ride.id))
    ride_created_signal.send(sender='create_pickmeapp_ride', obj=ride)

    return ride

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


def get_name_parts(full_name):
    if full_name is None:
        return None, None

    name_parts = re.split("\s+", full_name)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    return first_name.strip(), last_name.strip()


def create_user(username, password="", email="", first_name="", last_name="", save=True):
    user = User.objects.create_user(username, email, password)
    user.first_name = (first_name or "").strip()
    user.last_name = (last_name or "").strip()

    if email and not user.first_name:
        user.first_name = email.split("@")[0]

    if save:
        user.save()

    # welcome the new user
    if user.email:
        t = get_template("welcome_email.html")
        context = Context({'passenger_name': user.first_name or ''})

        send_mail_as_noreply(user.email, u"WAYbetter - %s" % ugettext("Shared Taxi Rides"), html=t.render(context))

    logging.info("welcome new user: %s" % user)
    return user


def update_user_details(user, **kwargs):
    """
    raises UpdateUserError if new email or username are registered to other users
    """
    logging.info("update_user_details %s" % kwargs)
    ALREADY_TAKEN_ERROR_MSG = ugettext("%s already registered")
    MULTIPLE_ERROR_MSG = ugettext("We're sorry but your %s appears to used by multiple users. Please contact support@waybetter.com to resolve this issue.")

    handled_fields = ["email", "username", "password", "phone"]
    new_email = kwargs.get("email")
    new_username = kwargs.get("username")
    new_password = kwargs.get('password')
    new_phone = kwargs.get('phone')

    if new_email and new_username: # new username and new email must match
        if new_email != new_username:
            raise UpdateUserError(ugettext("Username and email must match"))
    elif new_username: # check new username is not taken
        try:
            existing_user_username = User.objects.get(username=new_username)
        except User.DoesNotExist:
            existing_user_username = None
        except User.MultipleObjectsReturned:
            raise UpdateUserError(MULTIPLE_ERROR_MSG % ugettext("username"))

        if existing_user_username and existing_user_username != user:
            raise UpdateUserError(ALREADY_TAKEN_ERROR_MSG % ugettext("username"))
    elif new_email and new_email != user.email: # check new email is not taken
        try:
            new_email_user = User.objects.get(email=new_email)
            if new_email_user:
                raise UpdateUserError(ALREADY_TAKEN_ERROR_MSG % ugettext("email"))

        except User.DoesNotExist:
            # updating email incurs updating the username
            user.username = new_email
            user.email = new_email

        except User.MultipleObjectsReturned:
            raise UpdateUserError(MULTIPLE_ERROR_MSG % ugettext("email"))

    if new_password:
        user.set_password(new_password)

    # update passenger's phone
    if new_phone:
        try:
            passenger = user.passenger
        except Passenger.DoesNotExist:
            raise UpdateUserError(ugettext("User is not a passenger"))

        if new_phone != passenger.phone:
            try:
                new_phone_passenger = Passenger.objects.get(phone=new_phone)
                if new_phone_passenger:
                    raise UpdateUserError(ALREADY_TAKEN_ERROR_MSG % ugettext("phone"))

            except Passenger.DoesNotExist:
                logging.info("updating passenger phone %s --> %s" % (passenger.phone, new_phone))
                passenger.phone = new_phone
                passenger.save()

            except Passenger.MultipleObjectsReturned:
                raise UpdateUserError(MULTIPLE_ERROR_MSG % ugettext("phone"))

    for k,v in kwargs.items():
        if k in handled_fields:
            continue
        elif v and getattr(user, k) != v:
            setattr(user, k, v)

    user.save()

    # local import to avoid import issues
    from billing.billing_manager import update_invoice_info
    update_invoice_info(user)

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
        user_id = user.id
        try:
            passenger = user.passenger
            passenger.user = None
            passenger.save()
        except Passenger.DoesNotExist:
            pass

        user.delete()
        logging.warn("delete user [%d, %s]: " % (user_id, user.username))


# notify us when users/passengers are deleted
from testing.selenium_helper import SELENIUM_USER_NAMES, SELENIUM_EMAIL
def post_delete_user(sender, instance, **kwargs):
    if instance.email == SELENIUM_EMAIL or instance.username in SELENIUM_USER_NAMES:
        pass
    else:
        logging.info("user deleted [%d, %s]" % (instance.id, instance.username))

def post_delete_passenger(sender, instance, **kwargs):
    if instance.user and (instance.user.email == SELENIUM_EMAIL or instance.user.username in SELENIUM_USER_NAMES):
        pass
    else:
        logging.info("passenger deleted [%d, %s]" % (instance.id, unicode(instance)))

models.signals.post_delete.connect(post_delete_user, sender=User)
models.signals.post_delete.connect(post_delete_passenger, sender=Passenger)
