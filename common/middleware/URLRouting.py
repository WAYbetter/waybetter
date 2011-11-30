import logging
from django.conf import settings

class URLRouting(object):
    """
    This middleware sets a different expiry age for cookies sent to mobile clients
    """
    @staticmethod
    def process_request(request):
        user_agent_parts = request.META.get("HTTP_USER_AGENT", "").split("/")
        if user_agent_parts:
            if user_agent_parts[0] == "WAYbetter" and user_agent_parts[1] == "iPhone":
                logging.info("using alternate urlconf: %s" % user_agent_parts)
                request.urlconf = "api_urls"
                request.mobile = True


