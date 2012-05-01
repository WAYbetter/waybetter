from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^hotspot/$', 'pricing.views.hotspot_pricing_overview', {'hotspot_id': None}),
    (r'^hotspot/(?P<hotspot_id>\d+)/$', 'pricing.views.hotspot_pricing_overview'),
)
