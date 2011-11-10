from datetime import datetime
import logging
from xml.dom import minidom
from django.core.urlresolvers import reverse
from django.utils.translation import get_language_from_request, ugettext as _
from common.util import get_unique_id, safe_fetch, get_text_from_element
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


def get_transaction_id(unique_id, lang_code, mpi_data):
    data = ALL_QUERY_FIELDS.copy()
#    unique_id = get_unique_id()

#    # save passenger in the session
#    request.session[unique_id] = passenger
    
    data.update(mpi_data)
    data.update({
        "terminal":         settings.BILLING["terminal_number"] + "s",
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

    res = safe_fetch(settings.BILLING["transaction_url"], method='POST', payload=data, deadline=10)
    if not res:
        return None
    elif res.content:
        logging.info(res.content)
        xml = minidom.parseString(res.content)
        txId = get_text_from_element(xml, "txId")
        return txId


def get_token_url(request, order=None):
    unique_id = get_unique_id()
    lang_code = get_language_from_request(request)

    if hasattr(request, "mobile") and request.mobile:
        mpi_data = settings.BILLING_MPI_MOBILE
    else:
        mpi_data = settings.BILLING_MPI

    if order:
        request.session[unique_id] = order

    trx_id = get_transaction_id(unique_id, lang_code, mpi_data)
    if trx_id:
        return settings.BILLING["token_url"] % trx_id
    else:
        request.session[ERROR_PAGE_TEXT] = _("Could not complete your registration. Please try again.")
        return reverse(error_page)
