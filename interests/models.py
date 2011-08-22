from common.models import BaseModel
from common.tz_support import UTCDateTimeField
from django.db import models
from django.utils.translation import ugettext_lazy as _
from common.util import phone_validator, notify_by_email
from ordering.models import Station
# Create your models here.
class MobileInterest(models.Model):
    email = models.EmailField(_("Email"))

    create_date = models.DateTimeField(_("create date"), auto_now_add=True)
    modify_date = models.DateTimeField(_("modify date"), auto_now=True)

    def notify(self):
        subject = "New mobile interest"
        msg = """
            from email: %s
            """ % (self.email)

        notify_by_email(subject, msg)


class StationInterest(models.Model):
    name = models.CharField(_("name"), max_length=60)
    city = models.CharField(_("city"), max_length=60)
    contact_person = models.CharField(_("contact person"), max_length=60)
    phone = models.CharField(_("phone"), max_length=60)

    create_date = models.DateTimeField(_("create date"), auto_now_add=True)
    modify_date = models.DateTimeField(_("modify date"), auto_now=True)

    def notify(self):
        subject = "New station interest"
        msg = """
        Station name: %s
        Contact person: %s
        City: %s
        Phone: %s
        """ % (self.name, self.contact_person, self.city, self.phone)

        notify_by_email(subject, msg)


class BusinessInterest(models.Model):
    contact_person = models.CharField(_("contact person"), max_length=60)
    phone = models.CharField(_("phone"), max_length=60, validators=[phone_validator])
    email = models.EmailField(_("Email"))
    from_station = models.ForeignKey(Station, default=None, null=True, blank=True)

    create_date = models.DateTimeField(_("create date"), auto_now_add=True)
    modify_date = models.DateTimeField(_("modify date"), auto_now=True)

    def __unicode__(self):
        return u"%s %s" % (self.contact_person, self.phone)

    def notify(self):
        subject = "New business interest"
        registration_link = 'www.waybetter.com/business_registration/?from_interest_id=%d' % self.id
        msg = """
        Contact person: %s
        Phone: %s
        Email: %s

        Registration form link: %s
        """ % (self.contact_person, self.phone, self.email, registration_link)

        notify_by_email(subject, msg)

class PilotInterest(BaseModel):
    email = models.CharField(max_length=50)
    location = models.CharField(max_length=20)

    create_date = UTCDateTimeField(_("create date"), auto_now_add=True)
    modify_date = UTCDateTimeField(_("modify date"), auto_now=True)
