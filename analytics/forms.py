from django import forms
from datetime import datetime
from django.utils.translation import gettext as _
from common.util import Enum

class AnalysisType(Enum):
    ORDERS = 1

class AnalysisScope(Enum):
    CITY =          1
    STATION =       2
    ALL =           3

class AnalyticsForm(forms.Form):
    start_date = forms.DateField(label=_("Start Date"))
    end_date = forms.DateField(label=_("End Date"))

    data_type = forms.ChoiceField(label=_("Type"), choices=AnalysisType.choices())
    data_scope = forms.ChoiceField(label=_("Scope"), choices=AnalysisScope.choices(), initial=AnalysisScope.ALL)

    city = forms.IntegerField(label=_("City"), widget=forms.Select(), required=False)
    station = forms.IntegerField(label=_("Station"), widget=forms.Select(), required=False)

    class Ajax:
        pass