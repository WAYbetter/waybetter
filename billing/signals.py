import logging
from common.decorators import receive_signal
from common.signals import AsyncSignal
from common.util import  Enum, notify_by_email

class BillingSignalType(Enum):
    APPROVED                    = 1
    FAILED                      = 2
    CHARGED                     = 3

billing_approved_signal = AsyncSignal(BillingSignalType.APPROVED, providing_args=["obj"])
billing_failed_signal   = AsyncSignal(BillingSignalType.FAILED, providing_args=["obj"])
billing_charged_signal  = AsyncSignal(BillingSignalType.CHARGED, providing_args=["obj"])

@receive_signal(billing_failed_signal)
def on_billing_trx_failed(sender, signal_type, obj, **kwargs):
    from billing.billing_backend import get_custom_message
    trx = obj
    sbj, msg = "Billing Failed [%s]" % sender, u""
    for att_name in ["id", "provider_status", "comments", "order", "passenger", "debug"]:
        msg += u"trx.%s: %s\n" % (att_name, getattr(trx, att_name))
    msg += u"custom msg: %s" % get_custom_message(trx.provider_status, trx.comments)
    logging.error(u"%s\n%s" % (sbj, msg))
    notify_by_email(sbj, msg=msg)
