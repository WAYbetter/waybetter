from django.contrib import admin
from ordering.models import SharedRide, RidePoint, Driver, Taxi

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
    list_display = ["id", "station_name", "number"]

    def station_name(self, obj):
        return obj.station.name

class DriverAdmin(admin.ModelAdmin):
    list_display = ["id", "station_name", "name"]

    def station_name(self, obj):
        return obj.station.name

admin.site.register(SharedRide, SharedRideAdmin)
admin.site.register(RidePoint, RidePointAdmin)
admin.site.register(Taxi, TaxiAdmin)
admin.site.register(Driver, DriverAdmin)
