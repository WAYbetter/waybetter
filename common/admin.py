from django.forms.models import ModelForm
from common.signals import SignalStore
from django.contrib import admin
from common.models import  City, CityArea

class CountryAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "code", "dial_code"]



class CityAreaInlineForm(ModelForm):
    class Meta:
        model = CityArea
        fields = ["name", "color", "points", "city"]

class CityAreaAdmin(admin.TabularInline):
    model = CityArea
    form = CityAreaInlineForm
    extra = 0


class CityAdmin(admin.ModelAdmin):
    inlines = [CityAreaAdmin]


class SignalStoreAdmin(admin.ModelAdmin):
    pass

#admin.site.register(Country,CountryAdmin)
admin.site.register(City, CityAdmin)
#admin.site.register(CityArea, CityAreaAdmin)
admin.site.register(SignalStore, SignalStoreAdmin)