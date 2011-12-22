from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^facebook_login/$', 'oauth2.views.facebook_login'),
)