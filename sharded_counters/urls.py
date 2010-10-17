from django.conf.urls.defaults import *

urlpatterns = patterns('sharded_counters.views',
    (r'increment/$', 'increment'),
    (r'show/$', 'show'),
    (r'', 'show'),
)
