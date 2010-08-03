from django.conf.urls.defaults import *
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    ('^$', 'django.views.generic.simple.direct_to_template',
     {'template': 'home.html'}),
    (r'^setup/$', 'common.views.setup'),
    (r'^admin/(.*)', admin.site.root)
    
)
