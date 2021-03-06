import cgi

from common import urllib_adaptor as urllib
from django.conf import settings
from django.contrib import auth
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.core.urlresolvers import reverse
from oauth2.models import FacebookSession
import logging
from settings import DEFAULT_DOMAIN

def update_profile_fb(request, passenger_id, next):
    """
    Callback after passenger approved us to get his data from fb
    """
    logging.info("update facebook profile for passenger[%s]" % passenger_id)

    from ordering.models import Passenger
    passenger = Passenger.by_id(passenger_id)
    if passenger and request.GET.get('code'):
        args = {
            'client_id': settings.FACEBOOK_APP_ID,
            # redirect_uri MUST match the one passed in step1 (redirecting to fb)
            'redirect_uri': "http://%s%s" % (DEFAULT_DOMAIN, reverse(update_profile_fb, args=[passenger.id, next])),
            'client_secret': settings.FACEBOOK_APP_SECRET,
            'code': request.GET['code'],
            }

        url = 'https://graph.facebook.com/oauth/access_token?' +\
              urllib.urlencode(args)

        try:
            response = cgi.parse_qs(urllib.urlopen(url).read())
            logging.info("FB query: %s" % url)
            logging.info("FB response: %s" % response)

            access_token = response['access_token'][0]

            facebook_session = FacebookSession(access_token=access_token)
            profile = facebook_session.query('me', fields=['id', 'email', 'first_name', 'last_name', 'picture'])
            passenger.picture_url = profile['picture']['data']['url']
            passenger.fb_id = profile['id']
            passenger.save()
            logging.info("passenger picture updated: %s" % passenger.picture_url)
        except Exception, e:
            pass

    next = next or reverse("wb_home")
    return HttpResponseRedirect(next)


def facebook_login(request):
    from sharing.passenger_controller import post_login_redirect

    error = None
    redirect = reverse(post_login_redirect)

    if request.user.is_authenticated():
        return HttpResponseRedirect(redirect)

    if request.GET:
        if 'code' in request.GET:
            args = {
                'client_id': settings.FACEBOOK_APP_ID,
                'redirect_uri': settings.FACEBOOK_REDIRECT_URI,
                'client_secret': settings.FACEBOOK_APP_SECRET,
                'code': request.GET['code'],
                }

            url = 'https://graph.facebook.com/oauth/access_token?' +\
                  urllib.urlencode(args)
            response = cgi.parse_qs(urllib.urlopen(url).read())

            logging.info("FB query: %s" % url)
            logging.info("FB response: %s" % response)

            access_token = response['access_token'][0]
            expires = response['expires'][0]

            facebook_session = FacebookSession.objects.get_or_create(
                access_token=access_token,
            )[0]

            facebook_session.expires = expires
            facebook_session.save()

            #            logging.info("saved facebook_session id=%s" % facebook_session.id)

            user = auth.authenticate(token=access_token)
            if user:
                if user.is_active:
                    auth.login(request, user)
                    return HttpResponseRedirect(redirect)
                else:
                    error = 'AUTH_DISABLED'
            else:
                error = 'AUTH_FAILED'
        elif 'error_reason' in request.GET:
            error = 'AUTH_DENIED'

    template_context = {'settings': settings, 'error': error}
    return render_to_response('facebook_login.html', template_context, context_instance=RequestContext(request))

def cloudprint_login(request):
    # To make this work again, copy oauth2client and httlib2 libs out of google's SDK to root directory

    from oauth2client.client import OAuth2WebServerFlow

    flow = OAuth2WebServerFlow(client_id='1033367127714.apps.googleusercontent.com',
                               client_secret='t3EGg6LJGaRhkLBJR_yLeQCd',
                               scope='https://www.googleapis.com/auth/cloudprint', approval_prompt='force')
    auth_uri = flow.step1_get_authorize_url(redirect_uri='http://devguy.waybetter-app.appspot.com/oauth2/callback', )
    return HttpResponseRedirect(auth_uri)

def oauth2_callback(request):
    from oauth2client.client import OAuth2WebServerFlow

    flow = OAuth2WebServerFlow(client_id='1033367127714.apps.googleusercontent.com',
                               client_secret='t3EGg6LJGaRhkLBJR_yLeQCd',
                               scope='https://www.googleapis.com/auth/cloudprint')
    flow.redirect_uri = 'http://devguy.waybetter-app.appspot.com/oauth2/callback'

    code = request.GET.get("code")
    logging.info("code = '%s'" % code)
    credentials = flow.step2_exchange(code)
    logging.info("credentials: %s, %s" % (credentials.refresh_token, credentials.access_token))
    return HttpResponse(credentials.to_json())
