from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^track/order/$', 'fleet.views.get_order_status'),
    (r'^track/order/(?P<order_id>\d+)/$', 'fleet.views.get_order_status'),
    (r'^isr/tests$', 'fleet.views.isr_testpage'),
)