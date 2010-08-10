from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^passenger/$', 'ordering.views.passenger_home'),

)



#(r'^passenger/(?P<username>\w+)/$', 'ordering.views.passenger_home'),
