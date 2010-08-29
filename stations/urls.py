from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns('',
    (r'^station/home/$', 'stations.views.station_home'),
    (r'^stations/$', 'stations.views.stations_home'),
    (r'^%s$' % settings.STATION_LOGIN_URL[1:], 'stations.views.login'),

)



#(r'^passenger/(?P<username>\w+)/$', 'ordering.views.passenger_home'),
