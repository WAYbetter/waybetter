from django.db import models
from django.utils.translation import gettext_lazy as _

# Create your models here.
class MobileInterest(models.Model):

    email = models.EmailField(_("Email"))

    create_date = models.DateTimeField(_("create date"), auto_now_add=True)
    modify_date = models.DateTimeField(_("modify date"), auto_now=True)

