from django import forms
from datetime import datetime
from django.utils.translation import ugettext as _
from common.util import Enum, EventType

class AnalysisType(Enum):
    ORDERS          = 1
    RATINGS         = 2
    REGISTRATION    = 3
    TIMING          = 4

    @classmethod
    def get_event_types(cls, analysis_type):
        if analysis_type == cls.RATINGS:
            return [EventType.ORDER_RATED]
        elif analysis_type == cls.ORDERS:
            return [EventType.ORDER_BOOKED,
                    EventType.ORDER_REJECTED,
                    EventType.ORDER_IGNORED,
                    EventType.ORDER_ACCEPTED,
                    EventType.ORDER_FAILED,
                    EventType.ORDER_ERROR,
                    EventType.ORDER_ASSIGNED,
                    EventType.CROSS_COUNTRY_ORDER_FAILURE,
                    EventType.NO_SERVICE_IN_COUNTRY,
                    EventType.NO_SERVICE_IN_CITY,
                    EventType.UNREGISTERED_ORDER ]
        elif analysis_type == cls.REGISTRATION:
            return [EventType.PASSENGER_REGISTERED]

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