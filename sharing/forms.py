from django.contrib.auth.models import User
from django.forms.util import ErrorList
from django import forms
from django.core.exceptions import ValidationError
from common.forms import _clean_address
from common.widgets import EmailInput
from sharing.models import HotSpot, ProducerPassenger
from django.utils.translation import ugettext_lazy as _


class HotSpotServiceRuleAdminForm(forms.ModelForm):
    def clean(self):
        self.cleaned_data["from_hour"] = self.cleaned_data["from_hour"].replace(second=0, microsecond=0)
        self.cleaned_data["to_hour"] = self.cleaned_data["to_hour"].replace(second=0, microsecond=0)
        return self.cleaned_data


class HotSpotAdminForm(forms.ModelForm):
    class Meta:
        model = HotSpot

#    def clean_address(self):
#        return _clean_address(self)


class ConstraintsForm(forms.Form):
    time_const_min = forms.IntegerField(label="Time constraint in minutes")
    time_const_frac = forms.FloatField(label="Fractional Time constraint")

    def clean(self):
        if self.cleaned_data["time_const_frac"] and self.cleaned_data["time_const_min"]:
            raise ValidationError("Please specify only one time constraint")
        return self.cleaned_data

    def clean_time_const_frac(self):
        if self.cleaned_data["time_const_frac"] < 1:
            raise ValidationError("Fractional time constraint must be bigger than 1 ")
        elif self.cleaned_data["time_const_frac"] > 2:
            raise ValidationError("Fractional time constraint must be smaller than 2")
        else:
            return self.cleaned_data["time_const_frac"]


class ProducerPassengerForm(forms.ModelForm):
    class Meta:
        exclude = ["producer", "country", "geohash", "passenger"]
        model = ProducerPassenger

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
            raise ValidationError(_("Email already registered."))

        return self.cleaned_data["email"]