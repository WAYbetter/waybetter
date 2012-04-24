from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^track/ride/$', 'fleet.views.get_ride_status'),
    (r'^track/ride/(?P<ride_id>\d+)/$', 'fleet.views.get_ride_status'),

    (r'^isrproxy/update/ride/(?P<ride_id>\d+)/$', 'fleet.backends.isr_proxy.update_ride'),
    (r'^isr/tests$', 'fleet.views.isr_testpage'),
)