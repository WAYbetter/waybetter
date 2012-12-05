from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'add_place/$', 'geo.views.add_place'),
)

 