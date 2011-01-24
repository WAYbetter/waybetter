from django.forms.models import ModelForm
from models import MobileInterest

class MobileInterestForm(ModelForm):
    class Meta:
        model = MobileInterest

    class Ajax:
        pass