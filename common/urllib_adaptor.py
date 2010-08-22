from google.appengine.api.urlfetch import fetch
import urllib

class Request:
    url = ""
    headers = {}
    data = None

    def __init__(self, url, data=None, headers=None):
        self.url = url
        self.data = data
        if headers:
            self.headers = headers

    def get_method(self):
       if self.data:
           return "POST"
       else:
           return "GET"


class Response:
    content = ""
    status_code = 0
    headers = {}

    def __init__(self, content, status_code, headers):
        self.content = content
        self.status_code = status_code
        self.headers = headers

    def read(self, bytes=0):
        if (bytes > 0):
            return self.content[:bytes]
        else:
            return self.content

    def __unicode__(self):
        return self.content

    def __str__(self):
        return self.content

    def __repr__(self):
        return self.content

def urlopen(url, data=None):
    if isinstance(url, basestring):
        req = Request(url, data)
    else:
        req = url
        if data is not None:
            req.data = data

    fetch_response = fetch(req.url, payload=req.data, method=req.get_method(), headers=req.headers)
    return Response(fetch_response.content, fetch_response.status_code, fetch_response.headers)

def urlencode(query,doseq=0):
    return urllib.urlencode(query, doseq)