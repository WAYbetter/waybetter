from django.conf.urls.defaults import *
urlpatterns = patterns('',
    (r'^get/ride/$', 'fleet.views.get_ride'),
    (r'^get/ride/(?P<ride_id>\d+)/$', 'fleet.views.get_ride'),

    (r'^isr/tests$', 'fleet.views.isr_testpage'),
    (r'^isrproxy/get_all_positions/$', 'fleet.backends.isr_proxy.get_all_positions'),
    (r'^isrproxy/get_ongoing_rides/$', 'fleet.backends.isr_proxy.get_ongoing_rides'),
    (r'^isrproxy/update/status/$', 'fleet.backends.isr_proxy.update_status'),
    (r'^isrproxy/update/positions/$', 'fleet.backends.isr_proxy.update_positions'),
    (r'^isrproxy/create/nyride/(?P<ride_id>\d+)/$', 'fleet.views.create_ny_isr_ride'),
)