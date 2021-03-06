from django.contrib import admin
from common.forms import MandatoryInlineFormset
from pricing.models import RuleSet, TemporalRule, DiscountRule, Promotion, PromoCode


class TemporalRuleAdmin(admin.ModelAdmin):
    list_display = ["id", "rule_set_name", "name", "from_when", "to_when"]

    def rule_set_name(self, obj):
        return obj.rule_set.name

    def from_when(self, obj):
        if obj.from_date:
            return "%s %s" % (obj.from_date, obj.from_hour)
        else:
            return "%s %s" % (obj.from_weekday, obj.from_hour)

    def to_when(self, obj):
        if obj.to_date:
            return "%s %s" % (obj.to_date, obj.to_hour)
        else:
            return "%s %s" % (obj.to_weekday, obj.to_hour)


class InlineTemporalRuleAdmin(admin.TabularInline):
    model = TemporalRule
    formset = MandatoryInlineFormset
    extra = 1


class RuleSetAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "priority"]
    inlines = [InlineTemporalRuleAdmin]


class DiscountRuleAdmin(admin.ModelAdmin):
    pass


class PromotionAdmin(admin.ModelAdmin):
    class PromoCodeInlineAdmin(admin.StackedInline):
        model = PromoCode

    inlines = [PromoCodeInlineAdmin]

#admin.site.register(TemporalRule, TemporalRuleAdmin)
admin.site.register(RuleSet, RuleSetAdmin)
admin.site.register(DiscountRule, DiscountRuleAdmin)
admin.site.register(Promotion, PromotionAdmin)