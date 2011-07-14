from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^hotspot/$', 'sharing.views.hotspot_ordering_page'),
)