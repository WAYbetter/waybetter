from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'playground/$', 'geo.views.playground'),
    (r'get/places/$', 'geo.views.get_places'),
    (r'crud/place/$', 'geo.views.crud_place'),
)

 