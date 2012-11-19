import logging
import time

from django.contrib.sessions.middleware import SessionMiddleware as DjangoSessionMiddleware
from django.conf import settings
from django.utils.cache import patch_vary_headers
from django.utils.http import cookie_date
from django.utils.importlib import import_module

class SessionMiddleware(object):
    django_session_middleware = DjangoSessionMiddleware()

    def get_session_cookie_name(self, request):
        user_agent_suffix = request.META.get('HTTP_USER_AGENT').split(" ")[0].lower()
        return "%s_%s" % (settings.SESSION_COOKIE_NAME, user_agent_suffix)

    def is_workstation_request(self, request):
        user_agent = request.META.get("HTTP_USER_AGENT", "").lower()
        return "workstation" in user_agent and "waybetter" in user_agent

    def process_request(self, request):
        if self.is_workstation_request(request):
            logging.info("using custom session middleware")

            engine = import_module(settings.SESSION_ENGINE)
            session_key = request.COOKIES.get(self.get_session_cookie_name(request), None)
            request.session = engine.SessionStore(session_key)
        else:
            return self.django_session_middleware.process_request(request)

    def process_response(self, request, response):
        if self.is_workstation_request(request):
            """
            If request.session was modified, or if the configuration is to save the
            session every time, save the changes and set a session cookie.
            """
            try:
                accessed = request.session.accessed
                modified = request.session.modified
            except AttributeError:
                pass
            else:
                if accessed:
                    patch_vary_headers(response, ('Cookie',))
                if modified or settings.SESSION_SAVE_EVERY_REQUEST:
                    if request.session.get_expire_at_browser_close():
                        max_age = None
                        expires = None
                    else:
                        max_age = request.session.get_expiry_age()
                        expires_time = time.time() + max_age
                        expires = cookie_date(expires_time)
                        # Save the session data and refresh the client cookie.
                    request.session.save()
                    response.set_cookie(self.get_session_cookie_name(request), # WB: this is the only line we changed here, all the rest is the same as original SessionMiddleware
                                        request.session.session_key, max_age=max_age,
                                        expires=expires, domain=settings.SESSION_COOKIE_DOMAIN,
                                        path=settings.SESSION_COOKIE_PATH,
                                        secure=settings.SESSION_COOKIE_SECURE or None,
                                        httponly=settings.SESSION_COOKIE_HTTPONLY or None)
            return response
        else:
            return self.django_session_middleware.process_response(request, response)
