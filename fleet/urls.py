from django.conf.urls.defaults import *
urlpatterns = patterns('',
    (r'^get/ride/$', 'fleet.views.get_ride'),
    (r'^get/ride/(?P<ride_id>\d+)/$', 'fleet.views.get_ride'),

    (r'^isr/tests$', 'fleet.views.isr_testpage'),
    (r'^isr/status$', 'fleet.views.isr_status_page'),
    (r'^isr/services/get_rides/$', 'fleet.views.get_ride_events'),

    (r'^isrproxy/update/status/$', 'fleet.backends.isr_proxy.update_status'),
    (r'^isrproxy/update/positions/$', 'fleet.backends.isr_proxy.update_positions'),

    # TODO_WB: remove url and controller when ISR testing is done
    (r'^isrproxy/create/nyride/(?P<ride_id>\d+)/$', 'fleet.views.create_ny_isr_ride'),
)