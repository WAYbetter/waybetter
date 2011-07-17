import settings

class LanguageMiddleware:
    """
    This middleware overrides browser langauge defaults.
    """
    def process_request(self, request):
        # respect accept lang for iphone native app
        if request.META.get("HTTP_USER_AGENT", "").find("Darwin") < 0 and not request.session.get("browser_lang_overriden", None):
            request.session["browser_lang_overriden"] = True
            request.session['django_language'] = settings.LANGUAGE_CODE

  