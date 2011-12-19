import logging
from django.contrib.auth import models as auth_models
from oauth2.models import FacebookSession

class FacebookBackend:
    def authenticate(self, token=None):
        facebook_session = FacebookSession.objects.get(access_token=token)

        profile = facebook_session.query('me')

        try:
            user = auth_models.User.objects.get(username=profile['id'])
        except auth_models.User.DoesNotExist, e:
            user = auth_models.User(username=profile['id'])
            logging.info("creating FB user id=%s, profile=%s" % (profile['id'], profile))

        user.set_unusable_password()
        user.email = profile['email']
        user.first_name = profile['first_name']
        user.last_name = profile['last_name']
        user.save()

        try:
            FacebookSession.objects.get(uid=profile['id']).delete()
        except FacebookSession.DoesNotExist, e:
            pass

        facebook_session.uid = profile['id']
        facebook_session.user = user
        facebook_session.save()

        return user

    def get_user(self, user_id):
        try:
            return auth_models.User.objects.get(pk=user_id)
        except auth_models.User.DoesNotExist:
            return None