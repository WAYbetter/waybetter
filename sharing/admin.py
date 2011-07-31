from django.contrib import admin
from ordering.models import SharedRide, RidePoint, Driver, Taxi, TaxiDriverRelation
from common.forms import MandatoryInlineFormset
from sharing.models import HotSpot, HotSpotTag, HotSpotTimeFrame
from sharing.forms import HotSpotAdminForm, TimeFrameForm

class HotSpotTagAdmin(admin.TabularInline):
    model = HotSpotTag
    extra = 1

class HotSpotTimeFrameAdmin(admin.TabularInline):
    model = HotSpotTimeFrame
    form = TimeFrameForm
    formset = MandatoryInlineFormset
    extra = 1

class HotSpotAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "address"]
    exclude = ["geohash", "lat", "lon"]
    inlines = [HotSpotTagAdmin, HotSpotTimeFrameAdmin]
    form = HotSpotAdminForm

class SharedRideAdmin(admin.ModelAdmin):
    list_display = ["id", "create_date", "depart_time", "arrive_time", "status", "taxi_number", "driver_name"]

    def driver_name(self, obj):
        return obj.driver.name
    def taxi_number(self, obj):
        return obj.taxi.number

class RidePointAdmin(admin.ModelAdmin):
    list_display = ["id", "create_date", "stop_time", "type", "address", "ride_id"]

    def ride_id(self, obj):
        return obj.ride_id

class TaxiAdmin(admin.ModelAdmin):
    list_display = ["id", "dn_station_name", "number"]
    exclude = ["dn_station_name"]

class DriverAdmin(admin.ModelAdmin):
    list_display = ["id", "dn_station_name", "name"]
    exclude = ["dn_station_name"]

class TaxiDriverRelationAdmin(admin.ModelAdmin):
    list_display = ["id", "_driver", "_taxi", "dn_station_name"]
    list_filter = ["driver", "taxi"]
    exclude = ["dn_station_name"]
    
    def _driver(self, obj):
        driver = Driver.by_id(obj.driver_id)
        return driver

    def _taxi(self, obj):
        return Taxi.by_id(obj.taxi_id)

admin.site.register(HotSpot, HotSpotAdmin)
admin.site.register(SharedRide, SharedRideAdmin)
admin.site.register(RidePoint, RidePointAdmin)
admin.site.register(Taxi, TaxiAdmin)
admin.site.register(Driver, DriverAdmin)
admin.site.register(TaxiDriverRelation, TaxiDriverRelationAdmin)