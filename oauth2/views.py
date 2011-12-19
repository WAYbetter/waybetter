import cgi
from common import urllib_adaptor as urllib
from django.conf import settings
from django.contrib import auth
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.core.urlresolvers import reverse
from oauth2.models import FacebookSession
from sharing.passenger_controller import post_login_redirect
import logging

def facebook_login(request):
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

