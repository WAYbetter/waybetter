"""
Forms and validation code for user registration.

"""


from django.contrib.auth.models import User
from django import forms
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from common.models import Country, City
from ordering.models import LANGUAGE_CHOICES, Station


# I put this on all required fields, because it's easier to pick up
# on them with CSS or JavaScript if they have a class of "required"
# in the HTML. Your mileage may vary. If/when Django ticket #3515
# lands in trunk, this will no longer be necessary.
from djangotoolbox.widgets import BlobWidget
from djangotoolbox.fields import BlobField

attrs_dict = {'class': 'required'}

#class StationModelForm(forms.ModelForm):
#    class Meta:
#        model = Station


class StationRegistrationForm(forms.Form):
    """
    Form for registering a new user account.

    Validates that the requested username is not already in use, and
    requires the password to be entered twice to catch typos.

    Subclasses should feel free to add any additional validation they
    need, but should avoid defining a ``save()`` method -- the actual
    saving of collected user data is delegated to the active
    registration backend.

    """
    first_name = forms.CharField(widget=forms.TextInput(attrs=dict(attrs_dict,
                                                                   maxlength=30)),
                                 label=_("first name"))
    last_name = forms.CharField(widget=forms.TextInput(attrs=dict(attrs_dict,
                                                                  maxlength=30)),
                                label=_("last name"))
    name = forms.CharField(widget=forms.TextInput(attrs=dict(attrs_dict,
                                                                  maxlength=50)),
                                label=_("station name"))

    license_number = forms.CharField(widget=forms.TextInput(attrs=dict(attrs_dict,
                                                                       maxlength=30)),
                                     label=_("license number"))

    username = forms.RegexField(regex=r'^\w+$',
                                max_length=30,
                                widget=forms.TextInput(attrs=attrs_dict),
                                label=_("username"),
                                error_messages={'invalid': _("This value must contain only letters, numbers and underscores.")})

    password1 = forms.CharField(widget=forms.PasswordInput(attrs=attrs_dict, render_value=False),
                                label=_("password"))

    password2 = forms.CharField(widget=forms.PasswordInput(attrs=attrs_dict, render_value=False),
                                label=_("password (again)"))
    email = forms.EmailField(widget=forms.TextInput(attrs=dict(attrs_dict,
                                                               maxlength=75)),
                             label=_("email address"))

    country_choices = [(c.id, "%s (%s)" % (c.name, c.dial_code)) for c in Country.objects.all().order_by("name")]
    default_country = Country.objects.get(code=settings.DEFAULT_COUNTRY_CODE)
    country = forms.IntegerField(widget=forms.Select(attrs=attrs_dict, choices=country_choices), label=_("country"))
    country.initial = default_country.id

    city_choices = [(c.id, c.name) for c in City.objects.filter(country=default_country)]
    city = forms.IntegerField(widget=forms.Select(attrs=attrs_dict, choices=city_choices), label=_("City"))

    address = forms.CharField(widget=forms.TextInput(attrs=dict(attrs_dict,
                                                                maxlength=80)),
                              label=_("address"))
    language_choice = LANGUAGE_CHOICES
    language = forms.IntegerField(widget=forms.Select(attrs=attrs_dict, choices=language_choice), label=_("language"))

    website_url = forms.CharField(widget=forms.TextInput(attrs=dict(attrs_dict,
                                                                    maxlength=255)),
                                  label=_("website url"), required=False)

    local_phone = forms.RegexField(regex=r'^\d+$',
                                   max_length=20,
                                   widget=forms.TextInput(attrs=attrs_dict),
                                   label=_("local phone number"),
                                   error_messages={'invalid': _("The value must contain only numbers.")})



    logo = forms.FileField(widget=BlobWidget(attrs=dict(attrs_dict)), label=_("logo"), required=False)
#    logo = BlobField(widget=BlobWidget(attrs=dict(attrs_dict)), label=_("logo"), required=False)

    number_of_taxis = forms.IntegerField(widget=forms.TextInput(attrs=dict(attrs_dict,
                                                                           maxlength=30)),
                                         label=_("number of taxis"))

    description= forms.CharField(widget=forms.Textarea(attrs=dict(attrs_dict,
                                                                maxlength=80)),
                              label=_("description"), required=False)

    def clean_username(self):
        """
        Validate that the username is alphanumeric and is not already
        in use.
        
        """
        try:
            user = User.objects.get(username=self.cleaned_data['username'])
        except User.DoesNotExist:
            return self.cleaned_data['username']
        raise forms.ValidationError(_("A user with that username already exists."))

    def clean(self):
        """
        Verifiy that the values entered into the two password fields
        match. Note that an error here will end up in
        ``non_field_errors()`` because it doesn't apply to a single
        field.
        
        """
        if 'city' in self.cleaned_data:
            city = City.objects.get(id=self.cleaned_data['city'])
            self.cleaned_data['city'] = city

        if 'country' in self.cleaned_data:
            country = Country.objects.get(id=self.cleaned_data['country'])
            self.cleaned_data['country'] = country

        if 'password1' in self.cleaned_data and 'password2' in self.cleaned_data:
            if self.cleaned_data['password1'] != self.cleaned_data['password2']:
                raise forms.ValidationError(_("The two password fields didn't match."))
        return self.cleaned_data

class CodeVerificationForm(forms.Form):

    validation_code = forms.IntegerField(widget=forms.TextInput(attrs=dict(attrs_dict, maxlength=5)), label=_("Validation code"))

class RegistrationFormTermsOfService(StationRegistrationForm):
    """
    Subclass of ``RegistrationForm`` which adds a required checkbox
    for agreeing to a site's Terms of Service.
    
    """
    tos = forms.BooleanField(widget=forms.CheckboxInput(attrs=attrs_dict),
                             label=_(u'I have read and agree to the Terms of Service'),
                             error_messages={'required': _("You must agree to the terms to register")})


class RegistrationFormUniqueEmail(StationRegistrationForm):
    """
    Subclass of ``RegistrationForm`` which enforces uniqueness of
    email addresses.
    
    """
    def clean_email(self):
        """
        Validate that the supplied email address is unique for the
        site.
        
        """
        if User.objects.filter(email=self.cleaned_data['email']):
            raise forms.ValidationError(_("This email address is already in use. Please supply a different email address."))
        return self.cleaned_data['email']


class RegistrationFormNoFreeEmail(StationRegistrationForm):
    """
    Subclass of ``RegistrationForm`` which disallows registration with
    email addresses from popular free webmail services; moderately
    useful for preventing automated spam registrations.
    
    To change the list of banned domains, subclass this form and
    override the attribute ``bad_domains``.
    
    """
    bad_domains = ['aim.com', 'aol.com', 'email.com', 'gmail.com',
                   'googlemail.com', 'hotmail.com', 'hushmail.com',
                   'msn.com', 'mail.ru', 'mailinator.com', 'live.com',
                   'yahoo.com']
    
    def clean_email(self):
        """
        Check the supplied email address against a list of known free
        webmail domains.
        
        """
        email_domain = self.cleaned_data['email'].split('@')[1]
        if email_domain in self.bad_domains:
            raise forms.ValidationError(_("Registration using free email addresses is prohibited. Please supply a different email address."))
        return self.cleaned_data['email']
