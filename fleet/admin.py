from django.contrib import admin
from fleet.models import FleetManager

class FleetManagerAdmin(admin.ModelAdmin):
    pass

admin.site.register(FleetManager, FleetManagerAdmin)

