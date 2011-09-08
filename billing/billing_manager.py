from datetime import datetime
import logging
from google.appengine.api.urlfetch import fetch
from billing.enums import BillingStatus
from billing.models import BillingTransaction
from common.util import get_unique_id, custom_render_to_response
from django.conf import settings
from django.template.context import RequestContext
from ordering.decorators import passenger_required_no_redirect

TRANSACTION_URL = "https://cgmpiuat.creditguard.co.il/CGMPI_Server/CreateTransactionExtended"
ALL_QUERY_FIELDS = {
    "MID"					:               "",
    "userName"				:				"",
    "password"				:				"",
    "mainTerminalNumber"	:				"",
    "terminal"				:				"",
    "uniqueID"				:				"",
    "amount"				:				"",
    "currency"				:				"",
    "transactionType"		:				"",
    "creditType"			:				"",
    "transactionCode"		:				"",
    "authNumber"			:				"",
    "numberOfPayments"		:				"",
    "firstPayment"			:				"",
    "periodicalPayment"		:				"",
    "validationType"		:				"",
    "dealerNumber"			:				"",
    "description"			:				"",
    "email"					:				"",
    "langID"				:				"",
    "timestamp"				:				"",
    "clientIP"				:				"",
    "xRem"					:				"",
    "userData1"				:				"",
    "userData2"				:				"",
    "userData3"				:				"",
    "userData4"				:				"",
    "userData5"				:				"",
    "userData6"				:				"",
    "userData7"				:				"",
    "userData8"				:				"",
    "userData9"				:				"",
    "userData10"			:				"",
    "saleDetailsMAC"		:				""
}


def get_transaction_id(unique_id):
    data = ALL_QUERY_FIELDS.copy()
#    unique_id = get_unique_id()

#    # save passenger in the session
#    request.session[unique_id] = passenger
    
    data.update({
        "MID":              112,
        "userName":         "wiibet",
        "password":         "312.2BE#e704",
        "terminal":         "0962831",
        "uniqueID":         unique_id,
        "amount":           0,
        "currency":         "ILS",
        "transactionType":  "Debit",
        "creditType":       "RegularCredit",
        "transactionCode":  "Phone",
        "authNumber":       1234567, # used only for testing
        "validationType":   "Normal",
        "langID":           "EN",
        "timestamp":        datetime.now().replace(microsecond=0).isoformat() #"2011-10-22T15:44:53" #default_tz_now().isoformat()
    })

    # encode data without using urlencode
    data = "&".join(["%s=%s" % i for i in data.items()])
    
    logging.info(data)
    res = fetch(TRANSACTION_URL, method="POST", payload=data, deadline=10)
    if res.content.startswith("--"):
        logging.error("No transaction ID received: %s" % res.content)
        return None

    return res.content


def get_token_url(unique_id, order=None):
    trx_id = get_transaction_id(unique_id)
    return settings.BILLING["token_url"] % trx_id
