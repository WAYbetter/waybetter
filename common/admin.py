from django.forms.models import ModelForm
from django.contrib import admin
from common.models import  City, CityArea, Message

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


class MessageAdmin(admin.ModelAdmin):
  list_display = ('key','content',)
  search_fields = ('key', 'content')

admin.site.register(Message, MessageAdmin)
#admin.site.register(Country,CountryAdmin)
admin.site.register(City, CityAdmin)
#admin.site.register(CityArea, CityAreaAdmin)