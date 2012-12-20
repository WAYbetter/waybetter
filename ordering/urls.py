from django.conf.urls.defaults import *
from django.conf.urls.defaults import url

urlpatterns = patterns('',
    # TODO_WB: extract pickmeapp urls out of here
    url(r'^pickmeapp/$', 'ordering.passenger_controller.pickmeapp_home', name="pickmeapp"),
    (r'^pickmeapp/$', 'ordering.passenger_controller.passenger_home'),
    (r'^dl/$', 'ordering.passenger_controller.pickmeapp_home'),
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
    (r'^o/(?P<order_id>\d+)/$', 'ordering.passenger_controller.track_order'),
    (r'^get_order_position/(?P<order_id>\d+)/$', 'ordering.passenger_controller.get_order_position'),
    (r'^init_mock_positions/(?P<order_id>\d+)/$', 'ordering.passenger_controller.init_mock_positions'),

    (r'^passenger/logout/$', 'django.contrib.auth.views.logout'),
    (r'^workstation/logout/$', 'django.contrib.auth.views.logout'),
    (r'^orders/logout/$', 'django.contrib.auth.views.logout'),
    (r'^station/logout/$', 'django.contrib.auth.views.logout'),
    (r'^station/home/logout/$', 'django.contrib.auth.views.logout'),
    (r'^station/(?P<subdomain_name>\w+)/$', 'ordering.station_controller.station_page'),
    (r'^b/$', 'ordering.station_controller.station_business_page'),
    (r'^station/(?P<subdomain_name>\w+)/b/$', 'ordering.station_controller.station_business_page'),
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
    (r'^services/connected/$', 'ordering.station_controller.connected'),
    (r'^services/get_init_workstation_orders/$', 'ordering.station_controller.get_workstation_orders'),
    (r'^services/send_sms_verification/$', 'ordering.passenger_controller.send_sms_verification'),
    (r'^services/register_passenger/$', 'ordering.passenger_controller.register_passenger'),
    (r'^services/register_device/$', 'ordering.passenger_controller.register_device'),
    (r'^info/phone_activation/$', 'ordering.passenger_controller.phone_activation'),
    (r'^services/request_phone_activation/$', 'ordering.passenger_controller.request_phone_activation'),
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
    (r'^services/m2m_interest/$', 'ordering.passenger_controller.m2m_interest'),
    (r'^services/terms_for_station_app/$', 'ordering.passenger_controller.terms_for_station_app'),
    (r'^setup/init_pricing_rules/$', 'ordering.rules_controller.init_pricing_rules'),
    (r'^setup/upload_flat_rate_rules/$', 'ordering.rules_controller.setup_flat_rate_rules'),
    (r'^setup/do_flat_rate_rules_setup/$', 'ordering.rules_controller.do_setup_flat_rate_pricing_rules'),

    (r'^resources/station_mobile_redirect/(?P<subdomain_name>\w+)/$', 'ordering.station_controller.station_mobile_redirect'),

    (r'^queue/handle_dead_workstations/$', 'ordering.station_connection_manager.handle_dead_workstations'),
    (r'^services/ws_heartbeat/$', 'ordering.station_connection_manager.send_heartbeat'),
    (r'^ads/(?P<campaign_id>\w+)/', 'ordering.station_controller.campaign_handler'),

    # pages
    (r'^test/$', 'ordering.ordering_controller.staff_m2m'),
    (r'^booking/$', 'ordering.ordering_controller.booking_page', {'continued': False}, "booking_page"),
    (r'^booking/continued/$', 'ordering.ordering_controller.booking_page', {'continued': True}, "booking_continued"),
    (r'^booking/set_data/$', 'ordering.ordering_controller.set_current_booking_data'),

    # json
    (r'^get_offers/$', 'ordering.ordering_controller.get_offers'),
    (r'^book_ride/$', 'ordering.ordering_controller.book_ride'),
    (r'^cancel_order/$', 'ordering.ordering_controller.cancel_order'),
    (r'^sync_app_state/$', 'ordering.ordering_controller.sync_app_state'),
    (r'^get_ongoing_ride_details/$', 'ordering.ordering_controller.get_ongoing_ride_details'),
    (r'^update_push_token/$', 'ordering.passenger_controller.update_push_token'),
    (r'^get_order_billing_status/$', 'ordering.ordering_controller.get_order_billing_status'),
    (r'^get_private_offer/$', 'ordering.ordering_controller.get_private_offer'),
    (r'^get_history_suggestions/$', 'ordering.ordering_controller.get_history_suggestions'),
    (r'^get_previous_rides/$', 'ordering.ordering_controller.get_previous_rides'),
    (r'^get_next_rides/$', 'ordering.ordering_controller.get_next_rides'),
    (r'^get_passenger_picture/$', 'ordering.ordering_controller.get_picture'),
    (r'^update_passenger_picture/$', 'ordering.ordering_controller.update_picture'),
    (r'^track_event/$', 'ordering.ordering_controller.track_app_event'),
    (r'^fb_share/$', 'ordering.ordering_controller.fb_share'),
)



#(r'^passenger/(?P<username>\w+)/$', 'ordering.views.passenger_home'),
