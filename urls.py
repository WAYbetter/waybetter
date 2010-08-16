from django.conf.urls.defaults import *
from django.contrib import admin
import common

admin.autodiscover()

urlpatterns = patterns('',
    ('^$', 'django.views.generic.simple.direct_to_template',
     {'template': 'home.html'}),
    (r'^accounts/', include('registration.urls')),
#    (r'^accounts/login/$', 'django.contrib.auth.views.login'),
    (r'^common/', include('common.urls')),
    (r'^admin/(.*)', admin.site.root),
    (r'^', include('ordering.urls')),

    
)



#(r'^passenger/(?P<username>\w+)/$', 'ordering.views.passenger_home'),
