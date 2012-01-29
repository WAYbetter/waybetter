from datetime import datetime
import logging
from billing.models import BillingTransaction
from django.core.urlresolvers import reverse
from django.utils.translation import get_language_from_request, ugettext as _
from billing.signals import billing_failed_signal
from common.decorators import receive_signal
from common.util import get_unique_id, safe_fetch, notify_by_email, send_mail_as_noreply
from django.conf import settings
from common.views import ERROR_PAGE_TEXT, error_page

@receive_signal(billing_failed_signal)
def on_billing_trx_failed(sender, signal_type, obj, **kwargs):
    trx = obj
    sbj = "Billing Failed [%s]" % sender
    msg = u"trx.id: %s\ntrx.comments: %s" % (trx.id, trx.comments)
    logging.error(u"%s\n%s" % (sbj, msg))
    notify_by_email(sbj, msg=msg)


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


def get_transaction_id(lang_code, mpi_data):
    data = ALL_QUERY_FIELDS.copy()
#    unique_id = get_unique_id()

#    # save passenger in the session
#    request.session[unique_id] = passenger
    
    data.update(mpi_data)
    data.update({
        "terminal":         BILLING_INFO["terminal_number"],
        "uniqueID":         get_unique_id(), # this must be passed, although currently not used
        "amount":           0,
        "currency":         "ILS",
        "transactionType":  "Debit",
        "creditType":       "RegularCredit",
        "transactionCode":  "Phone",
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


def get_token_url(request):
    lang_code = get_language_from_request(request)

    if hasattr(request, "mobile") and request.mobile:
        mpi_data = BILLING_MPI_MOBILE
    else:
        mpi_data = BILLING_MPI

    trx_id = get_transaction_id(lang_code, mpi_data)
    if trx_id:
        return BILLING_INFO["token_url"] % trx_id
    else:
        request.session[ERROR_PAGE_TEXT] = _("Could not complete your registration. Please try again.")
        return reverse(error_page)


def get_billing_redirect_url(request, order, passenger):
    """
    returns a url the passenger should be redirected to continue registration/billing process
    """
    if hasattr(passenger, "billing_info"):
        if order:
            billing_trx = BillingTransaction(order=order, amount=order.price, debug=order.debug)
            billing_trx.save()
            return reverse("bill_order", args=[billing_trx.id])
        else:
            return reverse("wb_home")

    else:
        # redirect to credit guard
        # if there is an order we'll get here again by tx_ok with passenger.billing_info ('if' condition will be met)
        return get_token_url(request)