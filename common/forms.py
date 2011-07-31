from django import forms
from django.forms.models import BaseInlineFormSet
from django.utils.translation import ugettext_lazy as _

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