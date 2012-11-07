import logging
from django.http import HttpResponseRedirect
from django.utils.http import urlquote

VER_1_2_SERVER = 'dev.latest.waybetter-app.appspot.com'
VER_1_2_DOMAINS = [VER_1_2_SERVER, 'dev.waybetter-app.appspot.com']


def get_domain_uri(request, domain_name, secure=True):
    new_uri = '%s://%s%s%s' % (
        secure and request.is_secure() and 'https' or 'http',
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
        user_agent_parts = request.META.get("HTTP_USER_AGENT", "").split("/")
        if request.path.startswith("/api/") or \
           (user_agent_parts and user_agent_parts[0] == "WAYbetter" and user_agent_parts[1] == "iPhone"):
                logging.info("using alternate urlconf: %s" % user_agent_parts)
                request.urlconf = "api_urls"
                request.mobile = True
                request.wb_app = True

        # redirect app v1.2 users to VER_1_2_SERVER (unless if current host is already the redirect)
        host = request.get_host()
        if host not in VER_1_2_DOMAINS and ((user_agent_parts[0] == "WAYbetter" and user_agent_parts[2] == "1.2") or is_ws_1_2_module(request)):
            logging.info("redirecting v1.2: %s > %s" % (host, VER_1_2_SERVER))
            new_uri = get_domain_uri(request, VER_1_2_SERVER, secure=False)

            response = HttpResponseRedirect(new_uri)
            if not is_ws_1_2_module(request):
                response.status_code = 307  # causes PhoneGap client to resend POST data to new_uri

            return response

def is_ws_1_2_module(request):
    user_agent = request.META.get("HTTP_USER_AGENT", "")
    return user_agent.startswith("WAYbetterSharingWorkstation")