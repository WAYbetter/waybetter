import logging
from common.decorators import receive_signal
from common.signals import AsyncSignal
from common.util import  Enum, notify_by_email

class BillingSignalType(Enum):
    APPROVED                    = 1
    FAILED                      = 2
    CHARGED                     = 3

billing_approved_signal = AsyncSignal(BillingSignalType.APPROVED, providing_args=["obj", "callback_args"])
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


@receive_signal(billing_approved_signal)
def on_billing_trx_approved(sender, signal_type, obj, callback_args, **kwargs):
    from ordering.ordering_controller import billing_approved_book_order
    trx = obj
    if callback_args:
        ride_id = callback_args.get("ride_id")
        ride_data = callback_args.get("ride_data")
        if ride_id is not None and ride_data:
            billing_approved_book_order(ride_id, ride_data, trx.order)
        else:
            logging.warning("no ride_id or ride_data for on_billing_trx_approved")


