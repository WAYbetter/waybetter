from djangoappengine import main

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from ordering.station_connection_manager import workstation_connected, workstation_disconnected

class ChannelHandler(webapp.RequestHandler):
    def post(self, *args):
        channel_id = self.request.POST["from"]
        if self.request.path.endswith("/connected/"):
            workstation_connected(channel_id)
        else:
            workstation_disconnected(channel_id)

application = webapp.WSGIApplication([(".*", ChannelHandler)])

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
