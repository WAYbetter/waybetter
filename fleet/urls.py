from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^track/ride/$', 'fleet.views.get_ride_status'),
    (r'^track/ride/(?P<ride_id>\d+)/$', 'fleet.views.get_ride_status'),
    (r'^isr/tests$', 'fleet.views.isr_testpage'),
)