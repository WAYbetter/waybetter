from ordering.station_controller import station_page

STATION_DOMAINS = ["taxiapp.co.il"]
class StationDomainMiddleware(object):
    @staticmethod
    def get_station_domain(request):
        if request.path == "/": # only affect requests to root
            host = request.META.get("SERVER_NAME", None)
            for domain in STATION_DOMAINS:
                if host.endswith(domain):
                    return host.replace('www.','').split(".")[0].lower()

        return None

    def process_request(self, request):
        subdomain_name = self.get_station_domain(request) 

        if not subdomain_name or subdomain_name == 'taxiapp':
            return None # no redirect - continue normal processing
        else:
            return station_page(request, subdomain_name) # serve station page instead of normal home page

