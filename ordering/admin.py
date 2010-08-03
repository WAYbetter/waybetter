from django.contrib import admin
from ordering.models import Passenger, Order, OrderAssignment, Station, Dispatcher

class PassengerAdmin(admin.ModelAdmin):
    pass

class OrderAdmin(admin.ModelAdmin):
    pass

class StationAdmin(admin.ModelAdmin):
    pass

class OrderAssignmentAdmin(admin.ModelAdmin):
    pass

class DispatcherAdmin(admin.ModelAdmin):
    pass
    
admin.site.register(Passenger, PassengerAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(OrderAssignment, OrderAssignmentAdmin)
admin.site.register(Station, StationAdmin)
admin.site.register(Dispatcher, DispatcherAdmin)