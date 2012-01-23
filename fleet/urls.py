from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^auth/$', 'fleet.views.authenticate'),
    (r'^isr/$', 'fleet.views.isr_view'),
)