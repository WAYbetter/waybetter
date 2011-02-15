class NoCacheMiddleWare(object):
    def process_response(self, request, response):
        response["Cache-Control"] = "no-cache, no-store, max-age=0, must-revalidate"
        response["Pragma"] = "no-cache"
        response["Expires"] = "Fri, 01 Jan 1990 00:00:00 GMT"
        return response