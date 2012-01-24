import logging
from django.contrib.auth.models import User
from oauth2.models import FacebookSession
from ordering.util import create_user

class FacebookBackend:
    supports_inactive_user = False
    supports_object_permissions = False
    supports_anonymous_user = False

    def authenticate(self, token=None):
        facebook_session = FacebookSession.objects.get(access_token=token)

        profile = facebook_session.query('me')

        fb_username = "fb_%s" % profile['id']
        try:
            user = User.objects.get(username=fb_username)
            user.email = profile['email']
        except User.DoesNotExist, e:
            user = create_user(fb_username, email=profile['email'])
            logging.info("creating FB user: %s, profile=%s" % (fb_username, profile))

        user.set_unusable_password()
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
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None