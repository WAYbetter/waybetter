from google.appengine.api import taskqueue
from google.appengine.ext.db import is_in_transaction
from billing.enums import BillingStatus, BillingAction
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

class BillingTransaction(BaseModel):
    passenger = models.ForeignKey(Passenger, related_name="billing_transactions")
    order = models.ForeignKey(Order, related_name="billing_transactions")
    amount = models.FloatField() # Agorot, Cents
    status = StatusField(choices=BillingStatus.choices(), default=BillingStatus.PENDING)
    committed = models.BooleanField(default=False)
    charge_date = UTCDateTimeField(_("charge date"), blank=True, null=True)

    transaction_id = models.CharField(max_length=36)

    comments = models.CharField(max_length=255, blank=True, default="")
    auth_number = models.CharField(max_length=50, blank=True, null=True)

    # Denormalized fields
    dn_passenger_name = models.CharField(_("passenger name"))
    dn_pickup = models.CharField(_("pickup"))
    dn_dropoff = models.CharField(_("dropoff"))
    dn_pickup_time = UTCDateTimeField(_("pickup time"))

    @property
    def amount_in_cents(self):
        return int(self.amount * 100)

    def save(self, *args, **kwargs):
        if not is_in_transaction():
            try:
                order = self.order
                self.dn_pickup = order.from_raw
                self.dn_dropoff = order.to_raw
                self.dn_pickup_time = order.depart_time
                self.passenger = order.passenger
                self.dn_passenger_name = order.passenger.name
            except Order.DoesNotExist:
                pass

        super(BillingTransaction, self).save(*args, **kwargs)

    def change_status(self, old_value, new_value):
        return self._change_attr_in_transaction("status", old_value=old_value, new_value=new_value, safe=False)

    def _setup_charge_date(self):
#        self.charge_date = self.dn_pickup_time + timedelta(days=1)
        self.charge_date = self.dn_pickup_time + timedelta(minutes=15)

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
        self._setup_charge_date()
        self.save()

        self._commit_transaction(token=billing_info.token,
                                 amount=self.amount_in_cents,
                                 card_expiration=billing_info.expiration_date_formatted,
                                 action=BillingAction.COMMIT)


    def disable(self):
        self.change_status(BillingStatus.APPROVED, BillingStatus.CANCELLED)

    def enable(self):
        self.change_status(BillingStatus.CANCELLED, BillingStatus.APPROVED)

        self._setup_charge_date()
        self.save()
        self.charge(immediately=True)

    def charge(self, immediately=False):
        eta = datetime.now() if immediately else self.charge_date
        self._commit_transaction(token=self.passenger.billing_info.token,
                                 amount=self.amount_in_cents,
                                 card_expiration=self.passenger.billing_info.expiration_date_formatted,
                                 action=BillingAction.CHARGE, eta=eta)


    def _commit_transaction(self, token, amount, card_expiration, action, eta=None):
        billing_transaction_id = self.id
        task = taskqueue.Task(url=reverse("billing.views.billing_task"), params=locals(), eta=eta)

        q = taskqueue.Queue('orders')
        q.add(task)


add_formatted_date_fields([BillingTransaction])



# TODO: only for dev time
class BillingForm(ModelForm):
    class Meta:
        model = BillingTransaction
        fields = ["order", "amount"]
