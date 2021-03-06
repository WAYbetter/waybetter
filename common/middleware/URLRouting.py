import logging
from django.utils.http import urlquote


class URLRouting(object):
    """
    This middleware loads alternate urlconf file and handles redirects.
    """
    @staticmethod
    def process_request(request):
        app, device, version = None, None, None

        user_agent_parts = request.META.get("HTTP_USER_AGENT", "").split("/")
        if len(user_agent_parts) > 2:
            app, device, version = user_agent_parts[:3]

        if app == "WAYbetter":
            logging.info("WAYbetter mobile app detected")
            request.mobile = True
            request.wb_app = True


def is_ws_1_2_module(request):
    user_agent = request.META.get("HTTP_USER_AGENT", "")
    return user_agent.startswith("WAYbetterSharingWorkstation")

def get_domain_uri(request, domain_name, secure=True):
    new_uri = '%s://%s%s%s' % (
        secure and request.is_secure() and 'https' or 'http',
        domain_name,
        urlquote(request.path),
        (request.method == 'GET' and len(request.GET) > 0) and '?%s' % request.GET.urlencode() or ''
    )

    return new_uri