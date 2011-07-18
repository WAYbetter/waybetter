from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^hotspot/$', 'sharing.views.hotspot_ordering_page'),
    (r'^calculation_complete/$', 'sharing.views.ride_calculation_complete'),
)