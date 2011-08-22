from django.conf.urls.defaults import *
from django.conf.urls.defaults import url
from django.views.generic.simple import direct_to_template

urlpatterns = patterns('',
    (r'^$', 'ordering.passenger_controller.passenger_home'),
    (r'^pickmeapp/$', 'ordering.passenger_controller.pickmeapp_home'),
    (r'^info$', 'ordering.passenger_controller.info_pages'),
    (r'^workstation/(?P<workstation_id>\d+)$', 'ordering.station_controller.workstation_home'),
    (r'^orders/(?P<order_id>\d+)$', 'ordering.order_manager.order_status'),
    (r'^book_order/$', 'ordering.order_manager.book_order'),
    (r'^orders/history/$', 'ordering.passenger_controller.get_passenger_orders_history'),
    (r'^passenger/profile/$', 'ordering.passenger_controller.profile_page'),
    (r'^passenger/stations/$', 'ordering.passenger_controller.stations_tab'),
    (r'^business_tab/$', 'ordering.passenger_controller.business_tab'),
    (r'^business_registration/$', 'ordering.passenger_controller.business_registration'),
    (r'^station/profile/$', 'ordering.station_controller.station_profile'),
    (r'^station/download_workstation/$', 'ordering.station_controller.download_workstation'),
    (r'^station/history/$', 'ordering.station_controller.get_station_orders_history'),
    (r'^station/analytics/$', 'ordering.station_controller.station_analytics'),

    (r'^passenger/logout/$', 'django.contrib.auth.views.logout'),
    (r'^workstation/logout/$', 'django.contrib.auth.views.logout'),
    (r'^orders/logout/$', 'django.contrib.auth.views.logout'),
    (r'^station/logout/$', 'django.contrib.auth.views.logout'),
    (r'^station/home/logout/$', 'django.contrib.auth.views.logout'),
    (r'^station/(?P<subdomain_name>\w+)$', 'ordering.station_controller.station_page'),
    (r'^station/home/$', 'ordering.station_controller.station_home'),
    (r'^stations/$', 'ordering.station_controller.stations_home'),
    url(r'^stations/login/$', 'django.contrib.auth.views.login' ,
        {'template_name': 'station_home.html'},
        name="station_login"),

    # services
    (r'^services/resolve_address/$', 'ordering.passenger_controller.resolve_address'),
    (r'^services/resolve_station_address/$', 'ordering.station_controller.resolve_address'),
    (r'^services/resolve_coordinates/$', 'ordering.passenger_controller.resolve_coordinates'),
    (r'^services/get_order_address/$', 'ordering.passenger_controller.get_order_address'),
    (r'^services/estimate_cost/$', 'ordering.passenger_controller.estimate_ride_cost'),
    (r'^services/book_order/$', 'ordering.passenger_controller.book_order'),
    (r'^services/redispatch_ignored/$', 'ordering.order_manager.redispatch_ignored_orders'),
    (r'^services/redispatch_pending/$', 'ordering.order_manager.redispatch_pending_orders'),
    (r'^services/update_future_pickup/$', 'ordering.order_manager.update_future_pickup'),
    (r'^services/show_order/$', 'ordering.station_controller.show_order'),
    (r'^services/get_stations/$', 'ordering.passenger_controller.get_stations'),
    (r'^services/get_tracker_init/$', 'ordering.passenger_controller.get_tracker_init'),
    (r'^services/set_favorite_station/$', 'ordering.passenger_controller.set_default_station'),
    (r'^services/update_order_status/$', 'ordering.station_controller.update_order_status'),
    (r'^services/update_online_status/$', 'ordering.station_controller.update_online_status'),
    (r'^services/message_received/$', 'ordering.station_controller.message_received'),
    (r'^services/get_current_version/$', 'ordering.station_controller.current_version'),
    (r'^services/get_init_workstation_orders/$', 'ordering.station_controller.get_workstation_orders'),
    (r'^services/send_sms_verification/$', 'ordering.passenger_controller.send_sms_verification'),
    (r'^services/register_passenger/$', 'ordering.passenger_controller.register_passenger'),
    (r'^services/change_credentials/$', 'ordering.passenger_controller.change_credentials'),
    (r'^services/validate_phone/$', 'ordering.passenger_controller.validate_phone'),
    (r'^services/check_phone_not_registered/$', 'ordering.passenger_controller.check_phone_not_registered'),
    (r'^services/check_phone_registered/$', 'ordering.passenger_controller.check_phone_registered'),
    (r'^services/update_passenger_profile/$', 'ordering.passenger_controller.edit_profile'),
    (r'^services/login_passenger/$', 'ordering.passenger_controller.login_passenger'),
    (r'^services/login_workstation/$', 'ordering.station_controller.login_workstation'),
    (r'^check_auth/$', 'ordering.station_controller.workstation_auth'),
    (r'^services/delete_workstation/$', 'ordering.station_controller.delete_workstation'),
    (r'^services/get_order_status/(?P<order_id>\d+)$', 'ordering.order_manager.get_order_status'),
    (r'^services/rate_order/(?P<order_id>\d+)/$', 'ordering.order_manager.rate_order'),
    (r'^services/do_not_rate_order/(?P<order_id>\d+)/$', 'ordering.order_manager.do_not_rate_order'),
    (r'^services/update_station_rating/$', 'ordering.order_manager.update_station_rating'),
    (r'^services/get_orders/$', 'ordering.passenger_controller.get_passenger_orders_history_data'),
    (r'^services/get_station_orders/$', 'ordering.station_controller.get_station_orders_history_data'),
    (r'^services/get_station_assignments/$', 'ordering.station_controller.get_station_assignments_history_data'),
    (r'^services/get_cities_for_country/$', 'ordering.station_controller.get_cities_for_country'),
    (r'^services/check_connection_failed/$', 'ordering.station_controller.connection_check_failed'),
    (r'^services/check_connection_passed/$', 'ordering.station_controller.connection_check_passed'),
    (r'^services/confirm_sms/$', 'ordering.passenger_controller.sms_confirmation'),
    (r'^services/get_online_count/$', 'ordering.passenger_controller.get_ws_online_count'),
    (r'^services/pilot_interest/$', 'ordering.passenger_controller.pilot_interest'),

    (r'^setup/init_pricing_rules/$', 'ordering.rules_controller.init_pricing_rules'),
    (r'^setup/upload_flat_rate_rules/$', 'ordering.rules_controller.setup_flat_rate_rules'),
    (r'^setup/do_flat_rate_rules_setup/$', 'ordering.rules_controller.do_setup_flat_rate_pricing_rules'),

    (r'^resources/station_mobile_redirect/(?P<subdomain_name>\w+)/$', 'ordering.station_controller.station_mobile_redirect'),

    (r'^queue/handle_dead_workstations/$', 'ordering.station_connection_manager.handle_dead_workstations'),

    url(r'^landing_page/$',  direct_to_template, {"template": "landing_page.html"}),



)



#(r'^passenger/(?P<username>\w+)/$', 'ordering.views.passenger_home'),
