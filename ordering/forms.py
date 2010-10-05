# This Python file uses the following encoding: utf-8

from django.forms.models import ModelForm
from django import forms
from django.utils.translation import gettext as _

from ordering.models import Order
from common.models import Country, City


HIDDEN_FIELDS = ("from_country", "from_city", "from_street_address", "from_geohash", "from_lon", "from_lat",
                 "to_country", "to_city", "to_street_address", "to_geohash", "to_lon", "to_lat",)

class OrderForm(ModelForm):
    passenger = None

    # optional disambiguation choices
    from_address_choices = []
    to_address_choices = []
    disambiguation_choices = {}

    class Meta:
        model = Order
        fields = ["from_raw", "to_raw"]
        fields.extend(HIDDEN_FIELDS)

    def __init__(self, data=None, passenger=None):
        super(ModelForm, self).__init__(data)
        self.passenger = passenger
        self.disambiguation_choices = {}

    def save(self, commit=True):
        #TODO_WB: geocode raw address, fill city_area
        
        model = super(OrderForm, self).save(commit=False)
        model.passenger = self.passenger

        model.form_postal_code = '000000'
        model.to_postal_code = '000000'

#        model.from_street_address = self.cleaned_data['from_raw']
#        model.to_street_address = self.cleaned_data['to_raw']

        if commit:
            model.save()

        return model

class StationProfileForm(forms.Form):
    station = None

    def __init__(self, data=None, station=None):
        super(forms.Form, self).__init__(data)
        self.station = station


    name = forms.CharField(label=_("Station name"))
    password = forms.CharField(label=_("Change password"), widget=forms.PasswordInput(), required=False)
    password2 = forms.CharField(label=_("Re-enter password"), widget=forms.PasswordInput(), required=False)
    country = forms.IntegerField(widget=forms.Select(choices=Country.country_choices()), label=_("Country"))
#    city = forms.IntegerField(widget=forms.Select(choices=City.), label=_("City"))
    address = forms.CharField(label=_("Address"))
    no_of_taxis = forms.RegexField( regex=r'^\d+$',
                                    max_length=4,
                                    widget=forms.TextInput(),
                                    label=_("No of taxis"),
                                    error_messages={'invalid': _("The value must contain only numbers.")})

    website_url = forms.CharField(label=_("Website URL"))
#    language = form.
    email = forms.EmailField(label=_("Email"))
    class Ajax:
        rules = [
            ('password2', {'equal_to_field': 'password'}),

        ]
        messages = [
            ('password2', {'equal_to_field': _("The two password fields didn't match.")}),
        ]

class PassengerProfileForm(forms.Form):
    email = forms.EmailField(label=_("Email"))

    password =  forms.CharField(label=_("Change password"), widget=forms.PasswordInput(), required=False)

    password2 = forms.CharField(label=_("Re-enter password"), widget=forms.PasswordInput(), required=False)

    country =   forms.IntegerField(widget=forms.Select(choices=Country.country_choices()), label=_("Country"))

    phone =     forms.RegexField( regex=r'^\d+$',
                                  max_length=20,
                                  widget=forms.TextInput(),
                                  label=_("Local mobile phone #"),
                                  error_messages={'invalid': _("The value must contain only numbers.")} )

    phone_verification_code = forms.IntegerField(widget=forms.HiddenInput(), required=False)
    
    class Ajax:
        rules = [
            ('password2', {'equal_to_field': 'password'}),

        ]
        messages = [
            ('password2', {'equal_to_field': _("The two password fields didn't match.")}),
        ]

    def clean(self):
        """
        Verifiy that the values entered into the two password fields
        match. Note that an error here will end up in
        ``non_field_errors()`` because it doesn't apply to a single
        field.

        """
        if 'country' in self.cleaned_data:
            country = Country.objects.get(id=self.cleaned_data['country'])
            self.cleaned_data['country'] = country
         
        return self.cleaned_data

    