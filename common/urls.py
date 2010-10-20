from django.conf.urls.defaults import *


urlpatterns = patterns('',
    (r'setup/$', 'common.views.setup'),
    (r'test_channel/$', 'common.views.test_channel'),    
    (r'init_countries/$', 'common.views.init_countries'),
    (r'is_username_available/$', 'common.services.is_username_available'), 
    (r'registration/get_login_form/$', 'common.registration.get_login_form'),
    (r'registration/get_registration_form/$', 'common.registration.get_registration_form'),
    (r'registration/get_phone_verification_form/$', 'common.registration.get_phone_form'), 
    (r'registration/get_phone_code_form/$', 'common.registration.get_phone_code_form'),


)

