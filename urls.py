import dbindexer
dbindexer.autodiscover()

from django.conf.urls.defaults import *
from django.contrib import admin
from api.urls import CURRENT_VERSION
admin.autodiscover()


urlpatterns = patterns('',
#    ('^$', 'django.views.generic.simple.direct_to_template', {'template': 'home.html'}),
#    (r'^accounts/login/$', 'django.contrib.auth.views.login'),

#    (r'^$', 'ordering.passenger_controller.landing_page'),
    (r'^$', 'sharing.passenger_controller.passenger_home'),
    url(r'^sharing/$', 'sharing.passenger_controller.passenger_home', name='wb_home'),

    (r'^dl/$', 'ordering.passenger_controller.passenger_home'),
    (r'^accounts/', include('registration.backends.station.urls')),
    (r'^api/v%d/' % CURRENT_VERSION, include('api.urls')),
    (r'^common/', include('common.urls')),
    (r'^billing/', include('billing.urls')),
    (r'^testing/', include('testing.urls')),
    (r'^admin/analytics/', 'analytics.views.analytics'),
    (r'^admin/', include(admin.site.urls)),
    (r'^', include('ordering.urls')),
    (r'^sharing/', include('sharing.urls')),
    (r'^', include('analytics.urls')),
    (r'^interests/', include('interests.urls')),
    (r'^', include('socialauth.urls')),
    (r'^i18n/', include('django.conf.urls.i18n')),

    (r'^favicon\.ico$', 'django.views.generic.simple.redirect_to', {'url': '/static/images/favicon.ico'}),
    (r'^sitemap\.xml$', 'django.views.generic.simple.direct_to_template', {'template': 'sitemap.xml', 'mimetype': 'text/xml'}),
    (r'^robots\.txt$', 'django.views.generic.simple.direct_to_template', {'template': 'robots.txt', 'mimetype': 'text/plain'}),
)

from django.conf import settings
if 'rosetta' in settings.INSTALLED_APPS:
    urlpatterns += patterns('',
        url(r'^rosetta/', include('rosetta.urls')),
    )



#(r'^passenger/(?P<username>\w+)/$', 'ordering.views.passenger_home'),
