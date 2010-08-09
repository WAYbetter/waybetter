from django.conf.urls.defaults import *


urlpatterns = patterns('',
    (r'resolve_address/$', 'common.services.resolve_address'),
    
)

