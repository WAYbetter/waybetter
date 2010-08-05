# This Python file uses the following encoding: utf-8

from django.forms.models import ModelForm
from django.utils.translation import gettext as _

from ordering.models import Order
from common.models import Country, City
from common.geocode import geocode, geohash_encode
from common.util import is_empty
from django.forms.util import ErrorList

UPDATE_ADDRESS_CHOICE_FUNC_NAME = "updateAddressChoice"
HIDDEN_FIELDS = ("from_country", "from_city", "from_street_address", "from_geohash",
                 "to_country", "to_city", "to_street_address", "to_geohash")

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

    def is_valid(self):
#        if not super(OrderForm, self).is_valid():
#            return False

        result = True
        for f in ('from_raw', 'to_raw'):
            if is_empty(self.data[f]):
                return False

            # check that the submitted value is equal to the geocoded value clicked
            if self.data['geocoded_%s' % f] != self.data[f]:
                geocoding_results = geocode(self.data[f])
                if len(geocoding_results) == 0:
                    if not f in self.errors:
                        self.errors[f] = ErrorList()
                    self.errors[f].append(_("Can't resolve address, please try adding more details"))
                    return False

                if len(geocoding_results) > 1:
                    self.disambiguation_choices[f] = build_choices_links(geocoding_results, f)
                    result = False

        return result

#    def clean(self):
#        super(OrderForm, self).clean()
#        for f in ('from_country', 'to_country'):
#            if f in self.cleaned_data:
#                self.cleaned_data[f] = Country.get_id_by_code(self.cleaned_data[f])
#
#        return self.cleaned_data


    def save(self, commit=True):
        #TODO_WB: geocode raw address, fill city_area, street_address, geohash
        
        model = super(OrderForm, self).save(commit=False)
        model.passenger = self.passenger

        model.form_postal_code = '000000'
        model.to_postal_code = '000000'

        model.from_street_address = self.cleaned_data['from_raw']
        model.to_street_address = self.cleaned_data['to_raw']

        if commit:
            model.save()

        return model


def build_choices_links(options, field_name):
    links = []
    function_name = UPDATE_ADDRESS_CHOICE_FUNC_NAME
    prefix = field_name.split("_")[0]

    for option in options:
        name = option["name"]
        street = option["street"]
        country = Country.get_id_by_code(option["country"])
        city = City.get_id_by_name_and_country(option["city"], country, add_if_not_found=True)  
        geohash = geohash_encode(option["lon"], option["lat"])

        link = u"javascript:{function_name}('{prefix}', '{name}', '{street}', '{city}', '{country}', '{geohash}')".format(**locals())
        links.append((link, name))

    return links
        

        
