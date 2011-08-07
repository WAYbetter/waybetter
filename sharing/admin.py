from django.contrib import admin
from common.forms import MandatoryInlineFormset
from sharing.models import HotSpot, HotSpotTag, HotSpotServiceRule, HotSpotCustomPriceRule, HotSpotTariffRule
from sharing.forms import HotSpotAdminForm, HotSpotServiceRuleAdminForm

class InlineHotSpotTagAdmin(admin.TabularInline):
    model = HotSpotTag
    extra = 1


class InlineHotSpotServiceRuleAdmin(admin.TabularInline):
    exclude = ["rule_set"]
    model = HotSpotServiceRule
    form = HotSpotServiceRuleAdminForm
    formset = MandatoryInlineFormset
    extra = 1


class InlineHotSpotCustomPriceRuleAdmin(admin.TabularInline):
    exclude = ["rule_set"]
    model = HotSpotCustomPriceRule
    #    formset = MandatoryInlineFormset
    extra = 1


class InlineHotSpotTariffRuleAdmin(admin.TabularInline):
    model = HotSpotTariffRule
    #    formset = MandatoryInlineFormset
    extra = 1


class HotSpotAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "address"]
    exclude = ["geohash", "lat", "lon"]
    inlines = [InlineHotSpotTagAdmin, InlineHotSpotServiceRuleAdmin, InlineHotSpotCustomPriceRuleAdmin, InlineHotSpotTariffRuleAdmin]
    form = HotSpotAdminForm


admin.site.register(HotSpot, HotSpotAdmin)
