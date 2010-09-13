import dbindexer
dbindexer.autodiscover()

from django.conf.urls.defaults import *
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
#    ('^$', 'django.views.generic.simple.direct_to_template', {'template': 'home.html'}),
#    (r'^accounts/login/$', 'django.contrib.auth.views.login'),
    (r'^accounts/', include('registration.backends.station.urls')),
    (r'^common/', include('common.urls')),
    (r'^admin/(.*)', admin.site.root),
    (r'^', include('ordering.urls')),
    (r'^', include('stations.urls')),
    (r'^', include('socialauth.urls')),
)

from django.conf import settings
if 'rosetta' in settings.INSTALLED_APPS:
    urlpatterns += patterns('',
        url(r'^rosetta/', include('rosetta.urls')),
    )



#(r'^passenger/(?P<username>\w+)/$', 'ordering.views.passenger_home'),
