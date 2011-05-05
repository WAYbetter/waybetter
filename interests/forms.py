from django.forms.models import ModelForm
from models import MobileInterest, StationInterest, BusinessInterest

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

    class Ajax:
        pass
