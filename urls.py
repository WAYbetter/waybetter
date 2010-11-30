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
    (r'^admin/analytics/', 'analytics.views.analytics'),
    (r'^admin/', include(admin.site.urls)),
    (r'^', include('ordering.urls')),
    (r'^', include('analytics.urls')),
    (r'^', include('socialauth.urls')),
    
    (r'^favicon\.ico$', 'django.views.generic.simple.redirect_to', {'url': '/static/images/favicon.ico'}),
)

from django.conf import settings
if 'rosetta' in settings.INSTALLED_APPS:
    urlpatterns += patterns('',
        url(r'^rosetta/', include('rosetta.urls')),
    )



#(r'^passenger/(?P<username>\w+)/$', 'ordering.views.passenger_home'),
