import logging
from django.http import HttpResponseRedirect
from django.utils.http import urlquote

VER_1_1_SERVER = 'dev.latest.waybetter-app.appspot.com'
VER_1_1_DOMAINS = [VER_1_1_SERVER, 'dev.waybetter-app.appspot.com']


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
                if request.path.startswith("/api/mobile/1.2"):
                    request.urlconf = "api_1_2_urls"
                else:
                    request.urlconf = "api_urls"
                request.mobile = True
                request.wb_app = True