from common.util import get_unique_id
from django.db import models
from django.utils.translation import ugettext_lazy as _

# Create your models here.
class APIUser(models.Model):
    name = models.CharField(_("name"), max_length=40)
    key = models.CharField(_("api user key"), max_length=40, unique=True, default=get_unique_id)
    active = models.BooleanField(_("active"), default=False)
    phone_validation_required = models.BooleanField(_("phone validation required"), default=True)

    def __unicode__(self):
        return self.name

    class Meta:
        ordering = ["id"]