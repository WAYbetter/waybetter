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

@receive_signal(billing_approved_signal)
def on_billing_trx_approved(sender, signal_type, obj, **kwargs):
    from common.util import  send_mail_as_noreply, notify_by_email
    from django.utils import translation
    from django.utils.translation import ugettext as _
    from sharing.passenger_controller import get_passenger_ride_email

    passenger = obj.passenger
    if passenger.user and passenger.user.email:
        order = obj.order
        current_lang = translation.get_language()
        translation.activate(order.language_code)

        msg = get_passenger_ride_email(obj, order, passenger)
        send_mail_as_noreply(passenger.user.email, _("WAYbetter Order Confirmation"), html=msg)
        notify_by_email("Order Confirmation [%s]%s" % (order.id, " (DEBUG)" if order.debug else "") , html=msg)

        translation.activate(current_lang)

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
