from django.contrib import admin
from analytics.models import AnalyticsEvent

class AnalyticsEventAdmin(admin.ModelAdmin):
    pass

admin.site.register(AnalyticsEvent,AnalyticsEventAdmin)  
