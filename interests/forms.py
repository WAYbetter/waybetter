from django import forms
from django.forms.models import ModelForm
from interests.models import PilotInterest, HotspotInterest, M2MInterest
from models import MobileInterest, StationInterest, BusinessInterest
from ordering.models import Station

class MobileInterestForm(ModelForm):
    class Meta:
        model = MobileInterest

    class Ajax:
        pass

class StationInterestForm(ModelForm):
    class Meta:
        model = StationInterest

    class Ajax:
        pass

class BusinessInterestForm(ModelForm):
    class Meta:
        model = BusinessInterest
        exclude = ['from_station']

    from_station = forms.ModelChoiceField(queryset=Station.objects.all(), widget=forms.HiddenInput, required=False)

    class Ajax:
        pass

    def save(self, commit=True):
        model = super(BusinessInterestForm, self).save(commit=False)
        model.from_station = self.cleaned_data['from_station']

        if commit:
            model.save()

        return model

class PilotInterestForm(ModelForm):
    class Meta:
        model = PilotInterest
        fields = ["email"]

    class Ajax:
        pass

class M2MInterestForm(ModelForm):
    class Meta:
        model = M2MInterest
        fields = ["email"]

    class Ajax:
        pass


class HotspotInterestForm(ModelForm):
    class Meta:
        model = HotspotInterest

    class Ajax:
        pass