from django.forms.models import ModelForm
from django.contrib import admin
from common.models import  City, CityArea, Message

class CountryAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "code", "dial_code"]


class CityAreaAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "city_name", "for_pricing"]

    def city_name(self, obj):
        if obj.city:
            return obj.city.name

        return ""

class CityAreaInlineForm(ModelForm):
    class Meta:
        model = CityArea
        fields = ["name", "color", "points", "city"]

class CityAreaInlineAdmin(admin.TabularInline):
    model = CityArea
    form = CityAreaInlineForm
    extra = 0
    ordering = ["_city_order"]


class CityAdmin(admin.ModelAdmin):
    inlines = [CityAreaInlineAdmin]


class MessageAdmin(admin.ModelAdmin):
  list_display = ('key','content',)
  search_fields = ('key', 'content')

admin.site.register(Message, MessageAdmin)
#admin.site.register(Country,CountryAdmin)
admin.site.register(City, CityAdmin)
admin.site.register(CityArea, CityAreaAdmin)