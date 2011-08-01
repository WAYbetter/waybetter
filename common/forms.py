from django import forms
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from django.utils.translation import ugettext_lazy as _
from common.geocode import geocode

class MandatoryInlineFormset(BaseInlineFormSet):
    """
    Inline formset for mandatory fields: at least one should be defined.
    """

    def clean(self):
        # get forms that actually have valid data
        count = 0
        for form in self.forms:
            try:
                if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                    count += 1
            except AttributeError:
                # annoyingly, if a subform is invalid Django explicity raises
                # an AttributeError for cleaned_data
                pass
        if count < 1:
            raise forms.ValidationError('Please define at least one.')


class DatePickerForm(forms.Form):
    """
    Date picker form for date format dd/mm/yyyy which is not supported by Django's datefield defaults.
    See: https://docs.djangoproject.com/en/dev/ref/forms/fields/#datefield
    """
    start_date = forms.DateField(label=_("Start Date"), input_formats=['%d/%m/%Y'])
    end_date = forms.DateField(label=_("End Date"), input_formats=['%d/%m/%Y'])

    class Ajax:
        pass


# common clean functions

def _clean_address(self):
    if "address" in self.initial and self.cleaned_data["address"] == self.initial["address"]:
        return self.initial["address"]

    result = None
    geocode_str = u"%s %s" % (self.cleaned_data["city"], self.cleaned_data["address"])
    geocode_results = geocode(geocode_str)
    if len(geocode_results) < 1:
        raise ValidationError("Could not resolve address")
    elif len(geocode_results) > 1:
        address_options = []
        for res in geocode_results:
            address = "%s %s" % (res["street_address"], res["house_number"])
            address_options.append(address)
            if address == self.cleaned_data["address"]:
                result = res
                break

        if not result:
            raise ValidationError("Please choose one: %s" % ", ".join(address_options))

    else:
        result = geocode_results[0]

    self.instance.lon = result["lon"]
    self.instance.lat = result["lat"]
    self.instance.geohash = result["geohash"]
    #        self.instance.save()

    self.cleaned_data["address"] = "%s %s" % (result["street_address"], result["house_number"])

    return self.cleaned_data["address"]
