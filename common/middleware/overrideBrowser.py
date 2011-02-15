import settings

class LanguageMiddleware:
    """
    This middleware overrides browser langauge defaults.
    """
    def process_request(self, request):
        if not request.session.get("browser_lang_overriden", None):
            request.session["browser_lang_overriden"] = True
            request.session['django_language'] = settings.LANGUAGE_CODE

  