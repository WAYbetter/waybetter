from django.conf.urls.defaults import *
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    ('^$', 'django.views.generic.simple.direct_to_template',
     {'template': 'home.html'}),
    (r'^setup/$', 'common.views.setup'),
    (r'^passenger/$', 'ordering.views.passenger_home'),
    (r'^accounts/login/$', 'django.contrib.auth.views.login'),
    (r'^admin/(.*)', admin.site.root)
    
)



#(r'^passenger/(?P<username>\w+)/$', 'ordering.views.passenger_home'),
