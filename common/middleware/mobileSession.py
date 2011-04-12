from django.conf import settings

class MobileSessionMiddleware(object):
    """
    This middleware sets a different expiry age for cookies sent to mobile clients
    """
    @staticmethod
    def process_request(request):
        if request.mobile:
            request.session.set_expiry(settings.MOBILE_SESSION_COOKIE_AGE)


  