from django.forms.models import ModelForm
from ordering.models import Order
from common.models import Country

class OrderForm(ModelForm):
    passenger = None

    class Meta:
        model = Order
        fields = ("from_raw", "to_raw")

    def __init__(self, data=None, passenger=None):
        super(ModelForm, self).__init__(data)
        self.passenger = passenger
        
    def save(self, commit=True):
        model = super(OrderForm, self).save(commit=False)
        model.passenger = self.passenger

        country = Country.objects.all()[0]
        model.from_country = country
        model.to_country = country

        city = country.cities.all()[0]
        model.from_city = city
        model.to_city = city

        model.form_postal_code = '000000'
        model.to_postal_code = '000000'

        model.from_street_address = 'parsed street address'
        model.to_street_address = 'parsed street address'

        model.from_geohash = 'geohash'
        model.to_geohash = 'geohash'

        if commit:
            model.save()

        return model


        

        
