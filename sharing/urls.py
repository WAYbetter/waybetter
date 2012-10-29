from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^gmaps/$', 'sharing.staff_controller.gmaps'),
    (r'^gmaps_resolve_address/$', 'sharing.staff_controller.gmaps_resolve_address'),
    (r'^gmaps_reverse_gecode/$', 'sharing.staff_controller.reverse_geocode'),

    (r'^track_rides/$', 'sharing.staff_controller.track_rides'),
    (r'^birdseye/$', 'sharing.staff_controller.birdseye_view'),
    (r'^eagleeye/$', 'sharing.staff_controller.eagle_eye'),
    (r'^eagleeye_data/$', 'sharing.staff_controller.eagle_eye_data'),
    (r'^kpi/$', 'sharing.staff_controller.kpi'),
    (r'^kpi_csv/$', 'sharing.staff_controller.kpi_csv'),
    (r'^count_q/$', 'sharing.staff_controller.count_query'),
    (r'^pickmeapp_orders_map/$', 'sharing.staff_controller.pickmeapp_orders_map'),
    (r'^sharing_orders_map/$', 'sharing.staff_controller.sharing_orders_map'),
    (r'^get_orders_map_data/$', 'sharing.staff_controller.get_orders_map_data'),
    (r'^passenger_csv/$', 'sharing.staff_controller.passenger_csv'),
    (r'^debug/$', 'sharing.staff_controller.staff_home'),
    (r'^send_orders_data_csv/$', 'sharing.staff_controller.send_orders_data_csv'),
    (r'^send_users_data_csv/$', 'sharing.staff_controller.send_users_data_csv'),
    (r'^view_user_orders/(?P<user_id>\d+)/$', 'sharing.staff_controller.view_user_orders'),
    url(r'^hotspot/$', 'sharing.staff_controller.hotspot_ordering_page',  kwargs={'is_textinput': False}, name='hotspot_select'),
    url(r'^hotspot/textinput/$', 'sharing.staff_controller.hotspot_ordering_page', kwargs={'is_textinput': True}, name='hotspot_textinput'),
    (r'^computation_statistics/$', 'sharing.staff_controller.ride_computation_stat'),
    (r'^computation_statistics/(?P<computation_set_id>\d+)$', 'sharing.staff_controller.ride_computation_stat'),

    (r'^passenger/home/$', 'sharing.passenger_controller.passenger_home'),
    (r'^qr/\w+/$', 'sharing.passenger_controller.passenger_home'),
    (r'^arlozrovBridge/$', 'sharing.passenger_controller.passenger_home'),
    (r'^arlozrovCards/$', 'sharing.passenger_controller.passenger_home'),
    (r'^pg_home/$', 'sharing.passenger_controller.pg_home'),
    url(r'^user/profile/$', 'sharing.passenger_controller.user_profile', name="user_profile"),
    (r'^book_ride/$', 'sharing.passenger_controller.book_ride'),
    (r'^producer/ordering/$', 'sharing.producer_controller.producer_ordering_page'),
    (r'^producer/new_producer_passenger/$', 'sharing.producer_controller.new_producer_passenger'),
    (r'^producer/get_passengers/$', 'sharing.producer_controller.get_producer_passengers'),
    (r'^producer/rides_summary/$', 'sharing.producer_controller.producer_rides_summary'),
    (r'^ride/$', 'sharing.station_controller.show_ride'),
    (r'^ride/(?P<ride_id>\d+)/$', 'sharing.station_controller.show_ride'),
    (r'^accept_ride/$', 'sharing.station_controller.accept_ride'),
    (r'^complete_ride/$', 'sharing.station_controller.complete_ride'),
    (r'^calculation_complete/$', 'sharing.algo_api.ride_calculation_complete'),
    (r'^calculation_complete_noop/$', 'sharing.algo_api.ride_calculation_complete_noop'),
    (r'^submit_computations_task/$', 'sharing.algo_api.submit_computations_task'),
    (r'^submit_to_prefetch_task/$', 'sharing.algo_api.submit_to_prefetch_task'),
    url(r'^fax_received/$', 'sharing.station_controller.fax_received', name="fax_received"),
    url(r'^get_pending_faxes/$', 'sharing.station_controller.get_pending_faxes', name="get_pending_faxes"),
    (r'^send_dummy_fax/$', 'sharing.station_controller.send_dummy_fax_to_station'),
    (r'^services/resend_voucher/(?P<ride_id>\d+)/$', 'sharing.station_controller.resend_voucher'),
    url(r'^startup_message/$', 'sharing.passenger_controller.startup_message', name="startup_message"),

#    (r'^mark_ride_not_taken_task/$', 'sharing.sharing_dispatcher.mark_ride_not_taken_task'),
#    TODO_WB: resolve conflicts with ordering.urls
#    (r'^workstation/(?P<workstation_id>\d+)/$', 'sharing.station_controller.sharing_workstation_home'),
#    (r'^station/tools/$', 'sharing.station_controller.station_tools'),
#    (r'^station/history/$', 'sharing.station_controller.station_history'),
#    (r'^station/accounting/$', 'sharing.station_controller.station_accounting'),
#    (r'^station/taxidrivers/$', 'sharing.station_controller.station_taxidrivers'),
#    (r'^station/update_driver/$', 'sharing.station_controller.change_driver_details'),
#    (r'^station/delete_driver/$', 'sharing.station_controller.delete_driver'),
#    (r'^station/delete_taxi/$', 'sharing.station_controller.delete_taxi'),
#    (r'^station/create_taxidriver/$', 'sharing.station_controller.create_taxidriver_relation'),
#    (r'^station/delete_taxidriver/$', 'sharing.station_controller.delete_taxidriver_relation'),
#    (r'^drivers_for_taxi/$', 'sharing.station_controller.get_drivers_for_taxi'),
#    (r'^check_auth/$', 'sharing.station_controller.workstation_auth'),

    (r'^myrides_data/$', 'sharing.passenger_controller.get_myrides_data'),
    (r'^order_status/$', 'sharing.passenger_controller.get_order_status'),
    (r'^cancel_order/$', 'sharing.passenger_controller.cancel_order'),
    (r'^hotspots_data/$', 'sharing.passenger_controller.get_hotspots_data'),
    (r'^dates_for_hotspot/$', 'sharing.passenger_controller.get_hotspot_dates'),
    (r'^offers_for_hotspot/$', 'sharing.passenger_controller.get_hotspot_offers'),
    (r'^price_for_hotspot/$', 'sharing.passenger_controller.get_hotspot_price'),


    (r'^resolve_structured_address/$', 'sharing.passenger_controller.resolve_structured_address'),

    (r'^forgot_password/$', 'sharing.passenger_controller.verify_passenger'),
    (r'^change_credentials/$', 'sharing.passenger_controller.change_credentials'),

    (r'^registration/(?P<step>\w+)/$', 'sharing.passenger_controller.registration'),
    url(r'^registration/$', 'sharing.passenger_controller.registration', name="join"),
    url(r'^login_redirect/$', 'sharing.passenger_controller.post_login_redirect', name="login_redirect"),
    url(r'^send_verification_code/$', 'sharing.passenger_controller.send_sms_verification', name="send_verification_code"),
    url(r'^register_user/$', 'sharing.passenger_controller.do_register_user', name="register_user"),
    url(r'^register_passenger/$', 'sharing.passenger_controller.do_register_passenger', name="register_passenger"),
    url(r'^login_passenger/$', 'sharing.passenger_controller.passenger_login', name="login_passenger"),

    url(r'^info/$', 'sharing.content_controller.info', name="info"),
    url(r'^privacy/$', 'sharing.content_controller.privacy', name="privacy"),
    url(r'^terms/$', 'sharing.content_controller.terms', name="terms"),
    url(r'^contact/$', 'sharing.content_controller.contact', name="contact"),
    url(r'^faq/$', 'sharing.content_controller.faq', name="faq"),
    url(r'^the_service/$', 'sharing.content_controller.the_service', name="the_service"),
    url(r'^about/$', 'sharing.content_controller.about_us', name="about"),
    url(r'^welcome_email/$', 'sharing.content_controller.welcome_email'),

    url(r'^my_rides/$', 'sharing.content_controller.my_rides', name="my_rides"),

    url(r'^services/get_sharing_cities/$', 'sharing.content_controller.get_sharing_cities', name="get_sharing_cities"),
    url(r'^services/get_billing_url/$', 'sharing.passenger_controller.get_billing_url'),

    url(r'^cron/dispatch_rides/$', 'sharing.sharing_dispatcher.dispatching_cron'),



)
