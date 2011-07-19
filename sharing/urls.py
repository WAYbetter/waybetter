from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^hotspot/$', 'sharing.views.hotspot_ordering_page'),
    (r'^sharing_workstation_home/$', 'sharing.views.sharing_workstation_home'),
    (r'^accept_ride/$', 'sharing.views.accept_ride'),
    (r'^calculation_complete/$', 'sharing.views.ride_calculation_complete'),
)