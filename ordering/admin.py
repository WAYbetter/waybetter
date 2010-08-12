from django.contrib import admin
from ordering.models import Passenger, Order, OrderAssignment, Station, WorkStation

class PassengerAdmin(admin.ModelAdmin):
    pass

class OrderAdmin(admin.ModelAdmin):
    list_display = ["id", "station", "status", "pickup_time", "passenger"]
    list_filter = ["status", "station"]

class StationAdmin(admin.ModelAdmin):
    pass

class OrderAssignmentAdmin(admin.ModelAdmin):
    list_display = ["id", "station", "work_station", "order", "status"]
    list_filter = ["status", "work_station", "station" ]

class DispatcherAdmin(admin.ModelAdmin):
    pass
    
admin.site.register(Passenger, PassengerAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(OrderAssignment, OrderAssignmentAdmin)
admin.site.register(Station, StationAdmin)
admin.site.register(WorkStation, DispatcherAdmin)