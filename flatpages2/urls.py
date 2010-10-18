from django.conf.urls.defaults import *

urlpatterns = patterns('flatpages2.views',
    (r'^(?P<url>.*)$', 'flatpage'),
)
