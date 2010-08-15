from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^passenger/$', 'ordering.passenger_controller.passenger_home'),
    (r'^workstation/$', 'ordering.station_controller.workstation_home'),
    (r'^orders/(?P<order_id>\d+)$', 'ordering.order_manager.order_status'),
    (r'^book_order/$', 'ordering.order_manager.book_order'),

    # services
    (r'^service/update_order_status/$', 'ordering.station_controller.update_order_status'),
    (r'^service/get_orders/$', 'ordering.station_controller.get_orders'),
    (r'^service/get_workstation_orders/$', 'ordering.station_controller.get_workstation_orders'),
    (r'^service/get_order_status/(?P<order_id>\d+)$', 'ordering.order_manager.get_order_status'),

)



#(r'^passenger/(?P<username>\w+)/$', 'ordering.views.passenger_home'),
