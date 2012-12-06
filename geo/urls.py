from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'get_places/$', 'geo.views.get_places'),
    (r'crud_place/$', 'geo.views.crud_place'),
)

 