from django import forms
from django.utils.translation import ugettext_lazy as _

class DatePickerForm(forms.Form):
    """
    Date picker form for date format dd/mm/yyyy which is not supported by Django's datefield defaults.
    See: https://docs.djangoproject.com/en/dev/ref/forms/fields/#datefield
    """
    start_date = forms.DateField(label=_("Start Date"), input_formats=['%d/%m/%Y'])
    end_date = forms.DateField(label=_("End Date"), input_formats=['%d/%m/%Y'])

    class Ajax:
        pass