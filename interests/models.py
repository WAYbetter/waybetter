# This Python file uses the following encoding: utf-8
from django.template.context import Context
from django.template.loader import  render_to_string, get_template
from common.models import BaseModel
from django.db import models
from django.utils.translation import ugettext_lazy as _
from common.util import phone_validator, notify_by_email, send_mail_as_noreply
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
    email = models.EmailField(_("Your Email"))
    location = models.CharField(max_length=20, null=True, blank=True)

    def notify(self):
        subject = u"הצטרפו לפיילוט, קחו מונית, שלמו רק חצי - WAYbetter"
        t = get_template("pilot_interest_email.html")
        html = t.render(Context({}))
        send_mail_as_noreply(self.email, subject, html=html)

class HotspotInterest(BaseModel):
    suggestion = models.CharField(_("My Hotspot"), max_length=500)
    email = models.EmailField(_("My Email"))

    def notify(self):
        notify_by_email("New Votespot from %s" % self.email, msg=self.suggestion)
