from django.contrib import admin
from django.utils.translation import gettext as _
from ordering.models import Passenger, Order, OrderAssignment, Station, WorkStation, Phone, PricingRule
import station_connection_manager
from common.models import Country
from google.appengine.api.images import BadImageError

class PassengerAdmin(admin.ModelAdmin):
    list_display = ["id", "user_name"]

    def user_name(self, obj):
        if obj.user:
            return obj.user.username
        else:
            return "-- No User -- "

class OrderAdmin(admin.ModelAdmin):
    list_display = ["id", "station_name", "status", "pickup_time", "passenger"]
    list_filter = ["status", "station"]

    def station_name(self, obj):
        if obj.station:
            return obj.station.get_admin_link()

    station_name.allow_tags = True

class PhoneAdmin(admin.TabularInline):
    model = Phone
    extra = 2
    
class StationAdmin(admin.ModelAdmin):
    
    list_display = ["id", "name", "logo_img"]
    inlines = [PhoneAdmin]

    def logo_img(self, obj):
        res = _("No Logo")
        if obj.logo:
            import base64
            from google.appengine.api import images
            img = images.Image(obj.logo)
            img.resize(height=50)
            try:
                thumbnail = img.execute_transforms(output_encoding=images.PNG)
                res = u"""<img src='data:image/png;base64,%s' />""" % base64.encodestring(thumbnail)
            except BadImageError:
                pass


        return res

    logo_img.allow_tags = True

class OrderAssignmentAdmin(admin.ModelAdmin):
    list_display = ["id", "station_name", "work_station_name", "order_details", "status"]
    list_filter = ["status", "work_station", "station" ]

    def station_name(self, obj):
        return obj.station.get_admin_link()

    station_name.allow_tags = True

    def work_station_name(self, obj):
        return obj.work_station.get_admin_link()

    work_station_name.allow_tags = True

    def order_details(self, obj):
        return str(obj.order)

    

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


class PricingRuleAdmin(admin.TabularInline):
    model = PricingRule
    extra = 5
    

class CountryPricingRulesAdmin(admin.ModelAdmin):
    inlines = [PricingRuleAdmin,]
    
admin.site.register(Passenger, PassengerAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(OrderAssignment, OrderAssignmentAdmin)
admin.site.register(Station, StationAdmin)
admin.site.register(WorkStation, WorkStationAdmin)
admin.site.register(Country, CountryPricingRulesAdmin)