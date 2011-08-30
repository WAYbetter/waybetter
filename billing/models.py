from google.appengine.api import taskqueue
from google.appengine.ext.db import is_in_transaction
from billing.enums import BillingStatus
from common.models import BaseModel
from common.tz_support import UTCDateTimeField
from common.util import StatusField, add_formatted_date_fields
from django.core.urlresolvers import reverse
from ordering.models import Passenger, Order
from django.db import models
from django.utils.translation import ugettext_lazy as _

from datetime import datetime, timedelta

from django.forms.models import ModelForm


class InvalidOperationError(RuntimeError):
    pass


class BillingInfo(BaseModel):
    passenger = models.OneToOneField(Passenger, related_name="billing_info")
    token = models.CharField(max_length=20)
    expiration_date = models.DateField(_("expiration date"))
    card_repr = models.CharField(max_length=20)

    @property
    def expiration_date_formatted(self):
        return self.expiration_date.strftime("%m%y")

def setup_charge_date():
    return datetime.now() + timedelta(days=1)
#    return datetime.now() + timedelta(minutes=2)

class BillingTransaction(BaseModel):
    passenger = models.ForeignKey(Passenger, related_name="billing_transactions")
    order = models.ForeignKey(Order, related_name="billing_transactions")
    amount = models.IntegerField() # Agorot, Cents
    status = StatusField(choices=BillingStatus.choices(), default=BillingStatus.PENDING)
    committed = models.BooleanField(default=False)
    charge_date = UTCDateTimeField(_("charge date"), default=setup_charge_date)

    transaction_id = models.CharField(max_length=36)

    comments = models.CharField(max_length=255, blank=True, default="")
    auth_number = models.CharField(max_length=50, blank=True, null=True)

    # denormalized fields
    dn_passenger_name = models.CharField(_("passenger name"))
    dn_pickup = models.CharField(_("pickup"))
    dn_dropoff = models.CharField(_("dropoff"))
    dn_pickup_time = UTCDateTimeField(_("pickup time"))

    def save(self, *args, **kwargs):
        if not is_in_transaction():
            if self.order:
                self.dn_pickup = self.order.from_raw
                self.dn_dropoff = self.order.to_raw
                self.dn_pickup_time = self.order.pickup_point.stop_time
                self.passenger = self.order.passenger

            if self.passenger.user:
                self.dn_passenger_name  = self.passenger.user.username

        super(BillingTransaction, self).save(*args, **kwargs)

    def commit(self):
        """
        Submits this transaction to online billing provider

        Saves the BillingTransaction instance

        @return:
        """
        if self.committed:
            raise InvalidOperationError("This BillingTransaction was already committed")

        try:
            billing_info = self.passenger.billing_info
        except BillingInfo.DoesNotExist:
            raise InvalidOperationError("No billing info found for passenger: %s" % self.passenger)

        self._change_attr_in_transaction("committed", False, True, safe=False)

        result = self._commit_transaction(token=billing_info.token,
                                          amount=self.amount,
                                          card_expiration=billing_info.expiration_date_formatted,
                                          action="commit")


    def disable(self):
        self._change_attr_in_transaction("status", BillingStatus.APPROVED, BillingStatus.CANCELLED, safe=False)

    def enable(self):
        self._change_attr_in_transaction("status", BillingStatus.CANCELLED, BillingStatus.APPROVED, safe=False)

        self.charge_date = setup_charge_date()
        self.save()
        self.charge(immediately=True)

    def charge(self, immediately=False):
        eta = datetime.now() if immediately else self.charge_date
        result = self._commit_transaction(token=self.passenger.billing_info.token,
                                          amount=self.amount,
                                          card_expiration=self.passenger.billing_info.expiration_date_formatted,
                                          action="charge", eta=eta)


    def _commit_transaction(self, token, amount, card_expiration, action, eta=None):
        billing_transaction_id = self.id
        if action == "charge":
            task = taskqueue.Task(url=reverse("billing.views.billing_task"), params=locals(), eta=eta)
        else:
            task = taskqueue.Task(url=reverse("billing.views.billing_task"), params=locals())

        q = taskqueue.Queue('orders')
        q.add(task)


add_formatted_date_fields([BillingTransaction])



# TODO: only for dev time
class BillingForm(ModelForm):
    class Meta:
        model = BillingTransaction
        fields = ["order", "amount"]
