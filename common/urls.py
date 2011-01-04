from django.conf.urls.defaults import *
from django.views.generic.simple import direct_to_template


urlpatterns = patterns('',
    (r'setup/$', 'common.views.setup'),
    (r'test_channel/$', 'common.views.test_channel'),    
    (r' /$', 'common.views.init_countries'),
    (r'is_username_available/$', 'common.services.is_username_available'), 
    (r'registration/get_login_form/$', 'common.registration.get_login_form'),
    (r'registration/get_error_form/$', 'common.registration.get_error_form'),
    (r'registration/get_registration_form/$', 'common.registration.get_registration_form'),
    (r'registration/get_phone_verification_form/$', 'common.registration.get_phone_form'), 
    (r'registration/get_phone_code_form/$', 'common.registration.get_phone_code_form'),
    (r'registration/get_sending_form/$', 'common.registration.get_sending_form'),
    url(r'get_terms/$', direct_to_template, {'template': "terms_form.html"} ,name="terms_dialog"),

)

 