from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'token_form/$', 'billing.views.get_token'),
    (r'ride_csv_report/$', 'billing.views.get_csv'),
    (r'bill_passenger/$', 'billing.views.bill_passenger'),
    (r'tx_ok/$', 'billing.views.transaction_ok'),
    (r'tx_notok/$', 'billing.views.transaction_error'),
    (r'/tasks/billing/$', 'billing.views.billing_task'),

)

 