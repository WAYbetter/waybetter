from django.db.models.loading import get_model
from django.contrib.auth.models import User
from ordering.models import Passenger
from common.util import log_event, EventType

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