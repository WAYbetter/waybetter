from django.conf.urls.defaults import *
# manual loading so signal receivers code is evaluated
from sharing.sharing_dispatcher import ride_created
from sharing.passenger_controller import send_ride_notifications

urlpatterns = patterns('',
    (r'^debug/$', 'sharing.staff_controller.staff_home'),
    url(r'^hotspot/$', 'sharing.staff_controller.hotspot_ordering_page',  kwargs={'is_textinput': False}, name='hotspot_select'),
    url(r'^hotspot/textinput/$', 'sharing.staff_controller.hotspot_ordering_page', kwargs={'is_textinput': True}, name='hotspot_textinput'),
    (r'^computation_statistics/$', 'sharing.staff_controller.ride_computation_stat'),
    (r'^computation_statistics/(?P<computation_set_id>\d+)$', 'sharing.staff_controller.ride_computation_stat'),

    (r'^passenger/home/$', 'sharing.passenger_controller.passenger_home'),
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
    (r'^fetch_ride_results_task/$', 'sharing.algo_api.fetch_ride_results_task'),
    (r'^notify_passenger_task/$', 'sharing.passenger_controller.notify_passenger_task'),
    (r'^send_voucher_email/$', 'sharing.passenger_controller.send_ride_voucher'),
    (r'^push_ride_task/$', 'sharing.sharing_dispatcher.push_ride_task'),
    (r'^mark_ride_not_taken_task/$', 'sharing.sharing_dispatcher.mark_ride_not_taken_task'),
    (r'^workstation/(?P<workstation_id>\d+)/$', 'sharing.station_controller.sharing_workstation_home'),
    (r'^station/tools/$', 'sharing.station_controller.station_tools'),
    (r'^station/history/$', 'sharing.station_controller.station_history'),
    (r'^station/accounting/$', 'sharing.station_controller.station_accounting'),
    (r'^station/taxidrivers/$', 'sharing.station_controller.station_taxidrivers'),
    (r'^station/update_driver/$', 'sharing.station_controller.change_driver_details'),
    (r'^station/delete_driver/$', 'sharing.station_controller.delete_driver'),
    (r'^station/delete_taxi/$', 'sharing.station_controller.delete_taxi'),
    (r'^station/create_taxidriver/$', 'sharing.station_controller.create_taxidriver_relation'),
    (r'^station/delete_taxidriver/$', 'sharing.station_controller.delete_taxidriver_relation'),
    (r'^drivers_for_taxi/$', 'sharing.station_controller.get_drivers_for_taxi'),
    (r'^check_auth/$', 'sharing.station_controller.workstation_auth'),

    (r'^myrides_data/$', 'sharing.passenger_controller.get_myrides_data'),
    (r'^order_status/$', 'sharing.passenger_controller.get_order_status'),
    (r'^cancel_order/$', 'sharing.passenger_controller.cancel_order'),
    (r'^hotspots_data/$', 'sharing.passenger_controller.get_hotspots_data'),
    (r'^dates_for_hotspot/$', 'sharing.passenger_controller.get_hotspot_dates'),
    (r'^times_for_hotspot/$', 'sharing.passenger_controller.get_hotspot_times'),
    (r'^price_for_hotspot/$', 'sharing.passenger_controller.get_hotspot_price'),

    (r'^resolve_structured_address/$', 'sharing.passenger_controller.resolve_structured_address'),
    (r'^registration/(?P<order_id>\d+)/$', 'sharing.passenger_controller.registration'),
    url(r'^registration/$', 'sharing.passenger_controller.registration', name="join"),
    (r'^login_redirect/(?P<order_id>\d+)/$', 'sharing.passenger_controller.login_redirect'),
    url(r'^send_verification_code/$', 'sharing.passenger_controller.send_sms_verification', name="send_verification_code"),
    url(r'^validate_phone/$', 'sharing.passenger_controller.validate_phone', name="validate_phone"),
    url(r'^register/$', 'sharing.passenger_controller.do_register', name="register"),


    url(r'^info/$', 'sharing.content_controller.info', name="info"),
    url(r'^privacy/$', 'sharing.content_controller.privacy', name="privacy"),
    url(r'^terms/$', 'sharing.content_controller.terms', name="terms"),
    url(r'^contact/$', 'sharing.content_controller.contact', name="contact"),
    url(r'^the_service/$', 'sharing.content_controller.the_service', name="the_service"),
    url(r'^my_rides/$', 'sharing.content_controller.my_rides', name="my_rides"),

)
