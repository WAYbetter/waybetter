from django.conf.urls.defaults import *
# manual loading so signal receivers code is evaluated
from sharing.passenger_controller import send_ride_notifications
from sharing.sharing_dispatcher import *

urlpatterns = patterns('',
    url(r'^hotspot/$', 'sharing.passenger_controller.hotspot_ordering_page',  kwargs={'is_textinput': False}, name='hotspot_select'),
    url(r'^hotspot/textinput/$', 'sharing.passenger_controller.hotspot_ordering_page', kwargs={'is_textinput': True}, name='hotspot_textinput'),
    (r'^ride/$', 'sharing.station_controller.show_ride'),
    (r'^ride/(?P<ride_id>\d+)$', 'sharing.station_controller.show_ride'),
    (r'^computation_statistics/$', 'sharing.passenger_controller.ride_computation_stat'),
    (r'^computation_statistics/(?P<computation_set_id>\d+)$', 'sharing.passenger_controller.ride_computation_stat'),
    (r'^accept_ride/$', 'sharing.station_controller.accept_ride'),
    (r'^complete_ride/$', 'sharing.station_controller.complete_ride'),
    (r'^calculation_complete/$', 'sharing.views.ride_calculation_complete'),
    (r'^calculation_complete_noop/$', 'sharing.views.ride_calculation_complete_noop'),
    (r'^fetch_ride_results_task/$', 'sharing.views.fetch_ride_results_task'),
    (r'^notify_passenger_task/$', 'sharing.passenger_controller.notify_passenger_task'),
    (r'^mark_ride_not_taken_task/$', 'sharing.sharing_dispatcher.mark_ride_not_taken_task'),
    (r'^workstation/(?P<workstation_id>\d+)$', 'sharing.station_controller.sharing_workstation_home'),
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
    (r'^dates_for_hotspot/$', 'sharing.passenger_controller.get_hotspot_dates'),
    (r'^times_for_hotspot/$', 'sharing.passenger_controller.get_hotspot_times'),
    (r'^price_for_hotspot/$', 'sharing.passenger_controller.get_hotspot_price'),

)
