from django.db import models
from django.utils.translation import ugettext_lazy as _

# Create your models here.
class MobileInterest(models.Model):

    email = models.EmailField(_("Email"))

    create_date = models.DateTimeField(_("create date"), auto_now_add=True)
    modify_date = models.DateTimeField(_("modify date"), auto_now=True)

class StationInterest(models.Model):
    name = models.CharField(_("name"), max_length=60)
    city = models.CharField(_("city"), max_length=60)
    contact_person = models.CharField(_("contact person"), max_length=60)
    phone = models.CharField(_("phone"), max_length=60)

    create_date = models.DateTimeField(_("create date"), auto_now_add=True)
    modify_date = models.DateTimeField(_("modify date"), auto_now=True)
