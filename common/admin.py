from django.contrib import admin
from common.models import Country, City, CityArea

class CountryAdmin(admin.ModelAdmin):
    pass

class CityAdmin(admin.ModelAdmin):
    pass

class CityAreaAdmin(admin.ModelAdmin):
    pass

admin.site.register(Country,CountryAdmin)
admin.site.register(City,CityAdmin)
admin.site.register(CityArea,CityAreaAdmin)