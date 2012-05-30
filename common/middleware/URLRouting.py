import logging
from django.http import HttpResponseRedirect
from django.utils.http import urlquote

VER_1_1_DOMAIN = 'dev1p1.waybetter-app.appspot.com'

def get_domain_uri(request, domain_name):
    new_uri = '%s://%s%s%s' % (
        request.is_secure() and 'https' or 'http',
        domain_name,
        urlquote(request.path),
        (request.method == 'GET' and len(request.GET) > 0) and '?%s' % request.GET.urlencode() or ''
    )

    return new_uri


class URLRouting(object):
    """
    This middleware loads alternate urlconf file and handles redirects.
    """
    @staticmethod
    def process_request(request):
#        logging.info("Session ID = %s" % request.session.session_key)
        user_agent_parts = request.META.get("HTTP_USER_AGENT", "").split("/")
        if request.path.startswith("/api/") or \
           (user_agent_parts and user_agent_parts[0] == "WAYbetter" and user_agent_parts[1] == "iPhone"):
                logging.info("using alternate urlconf: %s" % user_agent_parts)
                request.urlconf = "api_urls"
                request.mobile = True
                request.wb_app = True

        # redirect app v1.1 users to VER_1_1_DOMAIN
        if user_agent_parts[:3] == ["WAYbetter", "iPhone", "1.1"]:
            logging.info("redirecting v1.1 to %s" % VER_1_1_DOMAIN)
            new_uri = get_domain_uri(request, VER_1_1_DOMAIN)

            response = HttpResponseRedirect(new_uri)
            response.status_code = 307 # causes PhoneGap client to resend POST data to new_uri
            return response

