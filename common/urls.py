from django.conf.urls.defaults import *
from django.views.generic.simple import direct_to_template


urlpatterns = patterns('',
    (r'setup/$', 'common.views.setup'),
    (r'test_channel/$', 'common.views.test_channel'),    
    (r' /$', 'common.views.init_countries'),
    (r'is_email_available/$', 'common.services.is_email_available'),
    (r'generate_dead_users_list/$', 'common.views.generate_dead_users_list'),
    (r'registration/get_login_form/$', 'common.registration.get_login_form'),
    (r'registration/get_error_form/$', 'common.registration.get_error_form'),
    (r'registration/get_registration_form/$', 'common.registration.get_registration_form'),
    (r'registration/get_credentials_form/$', 'common.registration.get_credentials_form'),
    (r'registration/get_phone_verification_form/$', 'common.registration.get_phone_form'),
    (r'registration/get_cant_login_form/$', 'common.registration.get_cant_login_form'),
    (r'registration/get_phone_code_form/$', 'common.registration.get_phone_code_form'),
    (r'registration/get_sending_form/$', 'common.registration.get_sending_form'),
    (r'feedback/$', 'common.registration.feedback'),
    (r'broadcast_signal/$', 'common.signals.send_async'),
    (r'flush_memcache/$', 'common.geocode.flush_memcache'),
    url(r'get_terms/$', direct_to_template, {'template': "terms_form.html"} ,name="terms_dialog"),

)

 