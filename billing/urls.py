from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'credit_guard_page/$', 'billing.views.credit_guard_page'),
    (r'ride_csv_report/$', 'billing.views.get_csv'),
    (r'bill_passenger/$', 'billing.views.bill_passenger'),
    url(r'tx_ok/$', 'billing.views.transaction_ok', name="trx_ok"),
    url(r'tx_notok/$', 'billing.views.transaction_error', name="trx_notok"),
    url(r'get_trx_status/$', 'billing.views.get_trx_status', name="get_trx_status"),
    url(r'bill_order/(?P<trx_id>\d+)/$', 'billing.views.bill_order', name="bill_order"),
    (r'/tasks/billing/$', 'billing.views.billing_task'),



    (r'send_invoices/$', 'billing.views.send_invoices'),

)

 