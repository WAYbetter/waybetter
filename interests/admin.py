from django.contrib import admin
from interests.models import MobileInterest, StationInterest, BusinessInterest

class MobileInterestAdmin(admin.ModelAdmin):
    pass
class StationInterestAdmin(admin.ModelAdmin):
    pass
class BusinessInterestAdmin(admin.ModelAdmin):
    pass

admin.site.register(MobileInterest, MobileInterestAdmin)
admin.site.register(StationInterest, StationInterestAdmin)
admin.site.register(BusinessInterest, BusinessInterestAdmin)