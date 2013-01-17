import settings
import logging

DJANGO_LANGUAGE = 'django_language'
BROWSER_LANG_OVERRIDEN = 'browser_lang_overriden'

class LanguageMiddleware:
    """
    This middleware overrides browser langauge defaults.
    """
    def process_request(self, request):
        if not request.session.get(BROWSER_LANG_OVERRIDEN):
            lang_to_set = None

            # respect 1.2.1 mobile app language preference
            if request.META.get("HTTP_LANGUAGE"):
                lang_to_set = request.META.get("HTTP_LANGUAGE")

            # respect accept lang for iphone native app
            elif request.META.get("HTTP_USER_AGENT", "").find("Darwin") < 0:
                lang_to_set =  settings.LANGUAGE_CODE

            if lang_to_set:
                logging.info("[process_request] settings language to %s" % lang_to_set)
                request.session[DJANGO_LANGUAGE] = lang_to_set
                request.session[BROWSER_LANG_OVERRIDEN] = True
  