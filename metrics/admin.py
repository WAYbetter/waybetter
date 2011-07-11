from django.contrib import admin
from models import StationMetric, WorkStationMetric

class ModelMetricAdmin(admin.ModelAdmin):
    # TODO_WB: if weights don't sum up to 1 log error and return something else
    list_display = ["id", "name", "weight", "function_name"]

admin.site.register(StationMetric, ModelMetricAdmin)
admin.site.register(WorkStationMetric, ModelMetricAdmin)
