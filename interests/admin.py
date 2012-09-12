from django.contrib import admin
from interests.models import MobileInterest, StationInterest, BusinessInterest, PilotInterest, HotspotInterest, M2MInterest

class MobileInterestAdmin(admin.ModelAdmin):
    pass
class StationInterestAdmin(admin.ModelAdmin):
    pass
class BusinessInterestAdmin(admin.ModelAdmin):
    pass

class HotspotInterestAdmin(admin.ModelAdmin):
    list_display = ["create_date", "email", "suggestion"]

class PilotInterestAdmin(admin.ModelAdmin):
    list_display = ["create_date", "email", "location"]

class M2MInterestAdmin(admin.ModelAdmin):
    list_display = ["create_date", "email"]


admin.site.register(MobileInterest, MobileInterestAdmin)
admin.site.register(StationInterest, StationInterestAdmin)
admin.site.register(BusinessInterest, BusinessInterestAdmin)
admin.site.register(PilotInterest, PilotInterestAdmin)
admin.site.register(M2MInterest, M2MInterestAdmin)
admin.site.register(HotspotInterest, HotspotInterestAdmin)