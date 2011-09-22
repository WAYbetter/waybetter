from django.contrib import admin
from interests.models import MobileInterest, StationInterest, BusinessInterest, PilotInterest

class MobileInterestAdmin(admin.ModelAdmin):
    pass
class StationInterestAdmin(admin.ModelAdmin):
    pass
class BusinessInterestAdmin(admin.ModelAdmin):
    pass

class PilotInterestAdmin(admin.ModelAdmin):
    list_display = ["create_date", "email", "location"]


admin.site.register(MobileInterest, MobileInterestAdmin)
admin.site.register(StationInterest, StationInterestAdmin)
admin.site.register(BusinessInterest, BusinessInterestAdmin)
admin.site.register(PilotInterest, PilotInterestAdmin)