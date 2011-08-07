from django.contrib import admin
from common.forms import MandatoryInlineFormset
from pricing.models import RuleSet, TemporalRule


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
    list_display = ["id", "name", "num_of_rules"]
    inlines = [InlineTemporalRuleAdmin]

    def num_of_rules(self, obj):
        return obj.rules.count()


#admin.site.register(TemporalRule, TemporalRuleAdmin)
admin.site.register(RuleSet, RuleSetAdmin)