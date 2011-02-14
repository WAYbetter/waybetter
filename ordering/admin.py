from common.util import blob_to_image_tag
from django.contrib import admin
from django.utils.translation import gettext as _
from django.forms.models import BaseInlineFormSet
from ordering.models import Passenger, Order, OrderAssignment, Station, WorkStation, Phone, MeteredRateRule, FlatRateRule, ExtraChargeRule, Feedback
import station_connection_manager
from common.models import Country
from google.appengine.api.images import BadImageError, NotImageError
from django.core.exceptions import ValidationError
import forms

from common.geocode import geocode

class PassengerAdmin(admin.ModelAdmin):
    list_display = ["id", "user_name", "phone"]

    def user_name(self, obj):
        if obj.user:
            return obj.user.username
        else:
            return "-- No User -- "

class OrderAdmin(admin.ModelAdmin):
    list_display = ["create_date_format", "station_name", "status", "pickup_time", "passenger", "passenger_rating"]
    list_filter = ["status", "station"]
    ordering = ['-create_date']

    def station_name(self, obj):
        if obj.station:
            return obj.station.get_admin_link()

    station_name.allow_tags = True

class PhoneInlineFormset(BaseInlineFormSet):
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
            raise forms.ValidationError('You must have at least one phone')

class PhoneAdmin(admin.TabularInline):
    model = Phone
    formset = PhoneInlineFormset
    extra = 2

def build_workstations(modeladmin, request, queryset):
    for station in queryset:
        station.delete_workstations()
        station.build_workstations()
build_workstations.short_description = "Build workstations"
    
class StationAdmin(admin.ModelAdmin):
    
    list_display = ["id", "name", "logo_img"]
    inlines = [PhoneAdmin]
    exclude = ["geohash", "lat", "lon", "number_of_ratings", "average_rating"]
    form = forms.StationAdminForm
    actions = [build_workstations]

    def logo_img(self, obj):
        res = ""
        if obj.logo:
            res = blob_to_image_tag(obj.logo, height=50)

        if not res:
            res = _("No Logo")
           
        return res
    logo_img.allow_tags = True

class OrderAssignmentAdmin(admin.ModelAdmin):
    list_display = ["create_date_format", "station_name", "work_station_name", "order_details", "status"]
    list_filter = ["status", "work_station", "station" ]
    ordering = ['-create_date']

    def station_name(self, obj):
        return obj.station.get_admin_link()

    station_name.allow_tags = True

    def work_station_name(self, obj):
        return obj.work_station.get_admin_link()

    work_station_name.allow_tags = True

    def order_details(self, obj):
        return unicode(obj.order)

    

class WorkStationAdmin(admin.ModelAdmin):
    list_display = ["id", "work_station_user", "station_name", "online_status"]

    def work_station_user(self, obj):
        return obj.get_admin_link()

    work_station_user.allow_tags = True

    def station_name(self, obj):
        return obj.station.get_admin_link()

    station_name.allow_tags = True

    def online_status(self, obj):
        if station_connection_manager.is_workstation_available(obj):
            return '<img src="%s">' % ("/static/img/online_small.gif")
        else:
            return ""
            
    online_status.allow_tags = True


class MeteredRateRuleAdmin(admin.TabularInline):
    model = MeteredRateRule
    extra = 5

class FlatRateRuleAdmin(admin.ModelAdmin):
    pass

class ExtraChargeRuleAdmin(admin.ModelAdmin):
    pass

class CountryPricingRulesAdmin(admin.ModelAdmin):
    inlines = [MeteredRateRuleAdmin,]

class FeedbackAdmin(admin.ModelAdmin):
    model = Feedback
    list_display = ["feedback"]
    list_filter = Feedback.field_names()

    def feedback(self, obj):
        return unicode(obj)
        
    feedback.allow_tags = True

    
admin.site.register(Passenger, PassengerAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(OrderAssignment, OrderAssignmentAdmin)
admin.site.register(Station, StationAdmin)
admin.site.register(WorkStation, WorkStationAdmin)
admin.site.register(Country, CountryPricingRulesAdmin)
admin.site.register(FlatRateRule, FlatRateRuleAdmin)
admin.site.register(Feedback, FeedbackAdmin)