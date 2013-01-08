import dbindexer
dbindexer.autodiscover()

from django.conf.urls.defaults import *
from django.contrib import admin
from api.urls import CURRENT_VERSION

# override the default ordering of ModelAdmin to avoid creating indexes of the form:
#- kind: myapp_mymodel
#  properties:
#  - name: __key__
#    direction: desc
from django.contrib.admin.options import BaseModelAdmin
BaseModelAdmin.ordering = ("id", )

admin.autodiscover()

baseurls = patterns('',
    (r'^$', 'ordering.ordering_controller.home', {}, 'wb_home'),
    (r'^noapps/$', 'ordering.ordering_controller.home', {'suggest_apps': False}, 'wb_home_noapps'),

    (r'^accounts/', include('registration.backends.station.urls')),
    (r'^oauth2/', include('oauth2.urls')),
    (r'^common/', include('common.urls')),
    (r'^geo/', include('geo.urls')),
    (r'^billing/', include('billing.urls')),
    (r'^fleet/', include('fleet.urls')),
    (r'^testing/', include('testing.urls')),
    (r'^admin/analytics/', 'analytics.views.analytics'),
    (r'^admin/cpanel/$', 'sharing.staff_controller.control_panel'),

    (r'^admin/', include(admin.site.urls)),
    (r'^', include('ordering.urls')),  # TODO_WB: prefix with pickmeapp - WILL BREAK WORKSTATION LOGIN
    (r'^', include('sharing.urls')),
    (r'^', include('analytics.urls')),
    (r'^interests/', include('interests.urls')),
    (r'^', include('socialauth.urls')),
    (r'^i18n/', include('django.conf.urls.i18n')),

    (r'^favicon\.ico$', 'django.views.generic.simple.redirect_to', {'url': '/static/images/favicon.ico'}),
    (r'^sitemap\.xml$', 'django.views.generic.simple.direct_to_template', {'template': 'sitemap.xml', 'mimetype': 'text/xml'}),
    (r'^robots\.txt$', 'django.views.generic.simple.direct_to_template', {'template': 'robots.txt', 'mimetype': 'text/plain'}),
)

apiurls = patterns('',
    (r'^api/v%d/' % CURRENT_VERSION, include('api.urls')),
    (r'', include(baseurls))
)

v1_2_urls = patterns('',
    (r'^faq/', 'django.views.generic.simple.direct_to_template', {'template': 'mobile/faq.html'}, "faq"),
    (r'', include(baseurls)),
)

v1_2_1_urls = patterns('',
    (r'^registration/$', 'ordering.account_controller.registration'),
    (r'^faq/', 'django.views.generic.simple.direct_to_template', {'template': 'mobile/faq.html'}, "faq"),
    (r'', include(baseurls)),
)

urlpatterns = patterns('',
    (r'^api/', include(apiurls)),
    (r'^api/mobile/1.2/', include(v1_2_urls)),
    (r'^api/mobile/1.2.1/', include(v1_2_1_urls)),
    (r'', include(baseurls)),
)