# This Python file uses the following encoding: utf-8

from django.forms.models import ModelForm
from django.utils.translation import gettext as _

from ordering.models import Order
from common.models import Country, City
from common.geocode import geocode, geohash_encode
from common.util import is_empty
from django.forms.util import ErrorList

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


        
