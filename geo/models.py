from django.db import models

class GoogleBounds(object):
    def __init__(self, values):
        self.sw_lat = values.get("sw_lat")
        self.sw_lon = values.get("sw_lon")
        self.ne_lon = values.get("ne_lon")
        self.ne_lat = values.get("ne_lat")

    def to_query_string(self):
        return "%s,%s|%s,%s" % (self.sw_lat, self.sw_lon, self.ne_lat, self.ne_lon)


class Place(models.Model):
    pass