from django.contrib import admin
from ordering.models import SharedRide, RidePoint

class SharedRideAdmin(admin.ModelAdmin):
    list_display = ["id", "create_date", "depart_time", "arrive_time"]


class RidePointAdmin(admin.ModelAdmin):
    list_display = ["id", "create_date", "stop_time", "type", "address", "ride_id"]

    def ride_id(self, obj):
        return obj.ride_id

admin.site.register(SharedRide, SharedRideAdmin)
admin.site.register(RidePoint, RidePointAdmin)
 