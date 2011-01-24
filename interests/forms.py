from django.forms.models import ModelForm
from interests.models import StationInterest
from models import MobileInterest

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