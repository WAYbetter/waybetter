from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^facebook_login/$', 'oauth2.views.facebook_login'),
    (r'^cp_login/$', 'oauth2.views.cloudprint_login'),
    (r'^callback/$', 'oauth2.views.oauth2_callback'),
)