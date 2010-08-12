from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^passenger/$', 'ordering.passenger_controller.passenger_home'),
    (r'^workstation/$', 'ordering.station_controller.workstation_home'),
    (r'^get_orders/$', 'ordering.station_controller.get_orders'),

)



#(r'^passenger/(?P<username>\w+)/$', 'ordering.views.passenger_home'),
