from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^mobile/$', 'interests.views.mobile_interest'),
    (r'^station/$', 'interests.views.station_interest'),
    (r'^business/$', 'interests.views.business_interest'),
)