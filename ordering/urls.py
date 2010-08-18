from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^passenger/$', 'ordering.passenger_controller.passenger_home'),
    (r'^signup_form.js$', 'ordering.passenger_controller.get_signup_form'),
    (r'^workstation/$', 'ordering.station_controller.workstation_home'),
    (r'^orders/(?P<order_id>\d+)$', 'ordering.order_manager.order_status'),
    (r'^orders/$', 'ordering.passenger_controller.get_orders'),
    (r'^book_order/$', 'ordering.order_manager.book_order'),

    (r'^passenger/logout/$', 'django.contrib.auth.views.logout'),
    (r'^workstation/logout/$', 'django.contrib.auth.views.logout'),
    (r'^orders/logout/$', 'django.contrib.auth.views.logout'),



    # services
    (r'^service/update_order_status/$', 'ordering.station_controller.update_order_status'),
    (r'^service/get_orders/$', 'ordering.station_controller.get_orders'),
    (r'^service/get_workstation_orders/$', 'ordering.station_controller.get_workstation_orders'),
    (r'^services/send_sms_verification/$', 'ordering.passenger_controller.send_sms_verification'),
    (r'^services/register_passenger/$', 'ordering.passenger_controller.register_passenger'),
    (r'^services/login_passenger/$', 'ordering.passenger_controller.login_passenger'),
    (r'^service/get_order_status/(?P<order_id>\d+)$', 'ordering.order_manager.get_order_status'),

)



#(r'^passenger/(?P<username>\w+)/$', 'ordering.views.passenger_home'),
