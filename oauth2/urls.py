from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'update_profile_fb/(?P<passenger_id>\d+)/$', 'oauth2.views.update_profile_fb'),
    (r'^facebook_login/$', 'oauth2.views.facebook_login'),
)