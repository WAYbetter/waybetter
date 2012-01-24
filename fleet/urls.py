from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^auth/$', 'fleet.views.authenticate'),
)