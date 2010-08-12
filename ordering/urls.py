from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^passenger/$', 'ordering.passenger_controller.passenger_home'),
    (r'^workstation/$', 'ordering.station_controller.workstation_home'),
    (r'^get_orders/$', 'ordering.station_controller.get_orders'),
    (r'^get_workstation_orders/$', 'ordering.station_controller.get_workstation_orders'),
    (r'^update_order_status/$', 'ordering.station_controller.update_order_status'),

)



#(r'^passenger/(?P<username>\w+)/$', 'ordering.views.passenger_home'),
