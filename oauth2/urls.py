from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'update_profile_fb/(?P<passenger_id>\d+)/next=(?P<next>.*)/$', 'oauth2.views.update_profile_fb'),
    (r'^facebook_login/$', 'oauth2.views.facebook_login'),
    (r'^cp_login/$', 'oauth2.views.cloudprint_login'),
    (r'^callback/$', 'oauth2.views.oauth2_callback'),
)