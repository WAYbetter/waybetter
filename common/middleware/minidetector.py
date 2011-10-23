    # Adapted from http://pub.mowser.com/wiki/Main/CodeExamples
# With a few additions by Moof
# The latest version of this file is always available from:
# http://minidetector.googlecode.com/svn/trunk/minidetector/search_strings.txt
#
# This list is public domain, please feel free to use it for your own projects
# If HTTP_USER_AGENT.lower() contains any of these strings, it's a mobile
# Also include some games consoles, see below

search_strings = [
        "sony",
        "symbian",
        "nokia",
        "samsung",
        "mobile",
        "windows ce",
        "epoc",
        "opera mini",
        "nitro",
        "j2me",
        "midp-",
        "cldc-",
        "netfront",
        "mot",
        "up.browser",
        "up.link",
        "audiovox",
        "blackberry",
        "ericsson,",
        "panasonic",
        "philips",
        "sanyo",
        "sharp",
        "sie-",
        "portalmmm",
        "blazer",
        "avantgo",
        "danger",
        "palm",
        "series60",
        "palmsource",
        "pocketpc",
        "smartphone",
        "rover",
        "ipaq",
        "au-mic,",
        "alcatel",
        "ericy",
        "up.link",
        "docomo",
        "vodafone/",
        "wap1.",
        "wap2.",
        "plucker",
        "480x640",
        "sec",
        "google wireless transcoder",
        "nintendo",
        "webtv",
        "playstation",
]

class Middleware(object):
    @staticmethod
    def process_request(request):
        """Adds a "mobile" attribute to the request which is True or False
           depending on whether the request should be considered to come from a
           small-screen device such as a phone or a PDA"""

#        # temporary hack to prevent mobile sniffing
#        request.mobile = True
#        return None

        # do not consider iPads as mobile
        if request.META.get("HTTP_USER_AGENT", "").lower().find("ipad") > -1:
            request.mobile = False
            return None

        if request.META.has_key("HTTP_X_OPERAMINI_FEATURES"):
            #Then it's running opera mini. 'Nuff said.
            #Reference from:
            # http://dev.opera.com/articles/view/opera-mini-request-headers/
            request.mobile = True
            return None

        if request.META.has_key("HTTP_ACCEPT"):
            s = request.META["HTTP_ACCEPT"].lower()
            if 'application/vnd.wap.xhtml+xml' in s:
                # Then it's a wap browser
                request.mobile = True
                return None

        if request.META.has_key("HTTP_USER_AGENT"):
            # This takes the most processing. Surprisingly enough, when I
            # Experimented on my own machine, this was the most efficient
            # algorithm. Certainly more so than regexes.
            # Also, Caching didn't help much, with real-world caches.
            s = request.META["HTTP_USER_AGENT"].lower()
            for ua in search_strings:
                if ua in s:
                    request.mobile = True
                    return None

        #Otherwise it's not a mobile
        request.mobile = False
        return None

def detect_mobile(view):
    """View Decorator that adds a "mobile" attribute to the request which is
       True or False depending on whether the request should be considered
       to come from a small-screen device such as a phone or a PDA"""

    def detected(request, *args, **kwargs):
        middleware.process_request(request)
        return view(request, *args, **kwargs)
    detected.__doc__ = "%s\n[Wrapped by detect_mobile which detects if the request is from a phone]" % view.__doc__
    return detected

def is_mobile_processor(request):
    return { 'mobile': request.mobile }

__all__ = ['Middleware', 'detect_mobile', 'is_mobile_processor']