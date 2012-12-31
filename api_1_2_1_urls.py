import dbindexer
dbindexer.autodiscover()

from django.conf.urls.defaults import *
from django.contrib import admin
from api.urls import CURRENT_VERSION
admin.autodiscover()

api_prefix = "api/mobile/1.2.1"

urlpatterns = patterns('',
#    ('^$', 'django.views.generic.simple.direct_to_template', {'template': 'home.html'}),
#    (r'^accounts/login/$', 'django.contrib.auth.views.login'),

    # 1.2 specific URLs
    (r'^%s/faq/' % api_prefix, 'django.views.generic.simple.direct_to_template', {'template': 'mobile/faq.html'}, "faq"),
    # end specific URLs

    (r'^$', 'ordering.ordering_controller.home', {}, 'wb_home'),

    (r'^%s/accounts/' % api_prefix, include('registration.backends.station.urls')),
    (r'^api/v%d/' % CURRENT_VERSION, include('api.urls')),
    (r'^%s/common/' % api_prefix, include('common.urls')),
    (r'^%s/geo/' % api_prefix, include('geo.urls')),
    (r'^%s/oauth2/' % api_prefix, include('oauth2.urls')),
    (r'^billing/', include('billing.urls')),
    (r'^testing/', include('testing.urls')),
    (r'^admin/analytics/', 'analytics.views.analytics'),
    (r'^admin/', include(admin.site.urls)),
    # TODO_WB: prefix with pickmeapp - WILL BREAK WORKSTATION LOGIN
    (r'^%s/' % api_prefix, include('ordering.urls')),
    (r'^%s/' % api_prefix, include('sharing.urls')),
    # hard code login_redirect url
    url(r'^login_redirect/$', 'sharing.passenger_controller.post_login_redirect', name="login_redirect"),
    (r'^', include('analytics.urls')),
    (r'^interests/', include('interests.urls')),
    (r'^', include('socialauth.urls')),
    (r'^i18n/', include('django.conf.urls.i18n')),

    (r'^favicon\.ico$', 'django.views.generic.simple.redirect_to', {'url': '/static/images/favicon.ico'}),
    (r'^sitemap\.xml$', 'django.views.generic.simple.direct_to_template', {'template': 'sitemap.xml', 'mimetype': 'text/xml'}),
    (r'^robots\.txt$', 'django.views.generic.simple.direct_to_template', {'template': 'robots.txt', 'mimetype': 'text/plain'}),
)

#(r'^passenger/(?P<username>\w+)/$', 'ordering.views.passenger_home'),
