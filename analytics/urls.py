from django.conf.urls.defaults import *


urlpatterns = patterns('',
    (r'services/log_event/$', 'analytics.views.log_event_on_queue'),
    (r'analytics/update_selects/$', 'analytics.views.update_scope_select'),

)

