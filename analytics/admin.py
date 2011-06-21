from django.contrib import admin
from analytics.models import AnalyticsEvent

class AnalyticsEventAdmin(admin.ModelAdmin):
    list_display = ["create_date", "type", "station"]

admin.site.register(AnalyticsEvent,AnalyticsEventAdmin)  
