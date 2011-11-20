from datetime import datetime
import logging
from django.core.urlresolvers import reverse
from django.utils.translation import get_language_from_request, ugettext as _
from common.util import get_unique_id, safe_fetch
from django.conf import settings
from common.views import ERROR_PAGE_TEXT, error_page

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

BILLING_INFO = settings.BILLING
BILLING_MPI = settings.BILLING_MPI
BILLING_MPI_MOBILE = settings.BILLING_MPI_MOBILE


def get_transaction_id(unique_id, lang_code, mpi_data):
    data = ALL_QUERY_FIELDS.copy()
#    unique_id = get_unique_id()

#    # save passenger in the session
#    request.session[unique_id] = passenger
    
    data.update(mpi_data)
    data.update({
        "terminal":         BILLING_INFO["terminal_number"],
        "uniqueID":         unique_id,
        "amount":           0,
        "currency":         "ILS",
        "transactionType":  "Debit",
        "creditType":       "RegularCredit",
        "transactionCode":  "Phone",
#        "authNumber":       1234567, # used only for testing
        "validationType":   "Normal",
        "langID":           (lang_code or settings.LANGUAGE_CODE).upper(),
        "timestamp":        datetime.now().replace(microsecond=0).isoformat() #"2011-10-22T15:44:53" #default_tz_now().isoformat()
    })

    # encode data without using urlencode
    data = "&".join(["%s=%s" % i for i in data.items()])
    
    logging.info(data)

    res = safe_fetch(BILLING_INFO["transaction_url"], method='POST', payload=data, deadline=10)
    if not res:
        return None
    elif res.content.startswith("--"):
        logging.error("No transaction ID received: %s" % res.content)
        return None
    else:
        return res.content


def get_token_url(request, order=None):
    unique_id = get_unique_id()
    lang_code = get_language_from_request(request)

    if hasattr(request, "mobile") and request.mobile:
        mpi_data = BILLING_MPI_MOBILE
    else:
        mpi_data = BILLING_MPI

    if order:
        request.session[unique_id] = order

    trx_id = get_transaction_id(unique_id, lang_code, mpi_data)
    if trx_id:
        return BILLING_INFO["token_url"] % trx_id
    else:
        request.session[ERROR_PAGE_TEXT] = _("Could not complete your registration. Please try again.")
        return reverse(error_page)
