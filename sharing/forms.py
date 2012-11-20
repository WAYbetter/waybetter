from django.contrib.auth.models import User
from django import forms
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from common.widgets import EmailInput
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _, ugettext

class UserRegistrationForm(forms.Form):
    order = None

    name = forms.CharField(label=_("Full Name"), required=True)
    email = forms.EmailField(label=_("Your Email"), required=True, widget=EmailInput)
    password = forms.CharField(label=_("Password"), widget=forms.PasswordInput(), required=True)
    re_password = forms.CharField(label=_("Re-Password"), widget=forms.PasswordInput(), required=True)
    agree_to_terms = forms.BooleanField(label=_("I agree to the Terms Of Use and Privacy Statement"), required=True)
    order_id = forms.IntegerField(widget=forms.HiddenInput(), required=False)

    class Ajax:
        rules = [('re_password', {'equal_to_field': 'password'})]
        messages = [('re_password', {'equal_to_field': _("The two password fields didn't match.")})]

    def clean(self):
        agree = self.cleaned_data.get("agree_to_terms")
        if not agree:
            self._errors["agree_to_terms"] = self.error_class([_("Please agree to our terms of service")])

        password = self.cleaned_data.get("password")
        re_password = self.cleaned_data.get("re_password")

        if password and re_password and not password == re_password:
            self._errors["password"] = self.error_class([_("The two password fields didn't match.")])
            del self.cleaned_data["password"]
            del self.cleaned_data["re_password"]

        return self.cleaned_data
        
    def clean_email(self):
        email = self.cleaned_data.get("email", "").lower().strip()
        self.cleaned_data["email"] = email

        try:
            user = User.objects.get(username=email)
        except User.DoesNotExist:
            user = None

        if user:
            link = "<a href=%s class='wb_link'>%s</a>" % (reverse('sharing.passenger_controller.verify_passenger'), ugettext("Forgot password?"))
            error_msg = "%s. %s" % (ugettext("Email already registered"), link)
            raise ValidationError(mark_safe(error_msg))

        return self.cleaned_data["email"]