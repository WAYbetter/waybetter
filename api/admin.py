from api.models import APIUser
from django.contrib import admin
class APIUserAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "key", "active", "phone_validation_required"]

admin.site.register(APIUser, APIUserAdmin)
