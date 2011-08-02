from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^hotspot/$', 'sharing.views.hotspot_ordering_page'),
    (r'^hotspot_page/$', 'sharing.passenger_controller.hotspot_page'),
    (r'^ride/$', 'sharing.views.show_ride'),
    (r'^ride/(?P<ride_id>\d+)$', 'sharing.views.show_ride'),
    (r'^accept_ride/$', 'sharing.views.accept_ride'),
    (r'^complete_ride/$', 'sharing.views.complete_ride'),
    (r'^calculation_complete/$', 'sharing.views.ride_calculation_complete'),
    (r'^fetch_ride_results_task/$', 'sharing.views.fetch_ride_results_task'),
    (r'^notify_driver_task/$', 'sharing.views.notify_driver_task'),
    (r'^notify_passenger_task/$', 'sharing.views.notify_passenger_task'),
    (r'^mark_ride_not_taken_task/$', 'sharing.sharing_dispatcher.mark_ride_not_taken_task'),
    (r'^workstation/(?P<workstation_id>\d+)$', 'sharing.views.sharing_workstation_home'),
    (r'^station/tools/$', 'sharing.views.station_tools'),
    (r'^station/history/$', 'sharing.views.station_history'),
    (r'^drivers_for_taxi/$', 'sharing.views.get_drivers_for_taxi'),
    (r'^dates_for_hotspot/$', 'sharing.passenger_controller.get_hotspot_dates'),
    (r'^times_for_hotspot/$', 'sharing.passenger_controller.get_hotspot_times'),

)