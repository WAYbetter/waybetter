from django.conf.urls.defaults import *


urlpatterns = patterns('',
    (r'resolve_address/$', 'common.services.resolve_address'),
    (r'setup/$', 'common.views.setup'),
    (r'test_channel/$', 'common.views.test_channel'),    
    (r'init_countries/$', 'common.views.init_countries'),
    (r'is_username_available/$', 'common.services.is_username_available'), 
)

