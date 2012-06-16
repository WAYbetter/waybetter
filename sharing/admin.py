from django.contrib import admin
from common.forms import MandatoryInlineFormset
from sharing.models import HotSpot, HotSpotTag, HotSpotServiceRule, HotSpotCustomPriceRule, HotSpotTariffRule, Producer, ProducerPassenger, HotSpotPopularityRule
from sharing.forms import HotSpotAdminForm, HotSpotServiceRuleAdminForm

class InlineHotSpotTagAdmin(admin.TabularInline):
    model = HotSpotTag
    extra = 1


class InlineHotSpotServiceRuleAdmin(admin.TabularInline):
    model = HotSpotServiceRule
    form = HotSpotServiceRuleAdminForm
    formset = MandatoryInlineFormset
    extra = 1


class InlineHotSpotPopularityRuleAdmin(admin.TabularInline):
    model = HotSpotPopularityRule
    extra = 1

class InlineHotSpotCustomPriceRuleAdmin(admin.TabularInline):
    model = HotSpotCustomPriceRule
    #    formset = MandatoryInlineFormset
    extra = 1


class InlineHotSpotTariffRuleAdmin(admin.TabularInline):
    model = HotSpotTariffRule
    #    formset = MandatoryInlineFormset
    extra = 1


class HotSpotAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "address", "is_public", "priority"]
    exclude = ["geohash"]
    inlines = [InlineHotSpotTagAdmin, InlineHotSpotServiceRuleAdmin, InlineHotSpotPopularityRuleAdmin]
    form = HotSpotAdminForm

class ProducerPassengerInlineAdmin(admin.TabularInline):
    model = ProducerPassenger
    fields = ["passenger", "name", "phone", "is_sharing", "address"]
    extra = 0
    
class ProducerAdmin(admin.ModelAdmin):
    inlines = [ProducerPassengerInlineAdmin]

admin.site.register(HotSpot, HotSpotAdmin)
admin.site.register(Producer, ProducerAdmin)