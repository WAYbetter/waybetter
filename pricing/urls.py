from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^hotspot/(?P<hotspot_id>\d+)/$', 'pricing.views.hotspot_pricing_overview'),
)
