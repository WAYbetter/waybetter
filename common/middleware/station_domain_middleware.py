from ordering.station_controller import station_page, get_station_domain
import re

qr_regexp = re.compile("/qr/\w*/*")

class StationDomainMiddleware(object):
    def process_request(self, request):
        if request.path == "/" or qr_regexp.match(request.path): # only affect requests to root and qr urls
            subdomain_name = get_station_domain(request)

            if subdomain_name and subdomain_name != 'taxiapp':
                return station_page(request, subdomain_name) # serve station page instead of normal home page

        return None # no redirect - continue normal processing


