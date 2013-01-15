import settings

class LanguageMiddleware:
    """
    This middleware overrides browser langauge defaults.
    """
    def process_request(self, request):
        lang_to_set = None

        # respect 1.2.1 mobile app language preference
        if request.META.get("HTTP_LANGUAGE"):
            lang_to_set = request.META.get("HTTP_LANGUAGE")

        # respect accept lang for iphone native app
        elif request.META.get("HTTP_USER_AGENT", "").find("Darwin") < 0 and not request.session.get("browser_lang_overriden", None):
            request.session["browser_lang_overriden"] = True
            lang_to_set =  settings.LANGUAGE_CODE


        if lang_to_set:
            request.session['django_language'] = lang_to_set

  