from django.utils.translation import ugettext as _
from django.contrib import admin
from common.forms import MandatoryInlineFormset
from django.core.urlresolvers import reverse
from ordering.models import RideComputation, RideComputationSet, Order
from sharing.models import HotSpot, HotSpotTag, HotSpotServiceRule, HotSpotCustomPriceRule, HotSpotTariffRule, Producer, ProducerPassenger
from sharing.forms import HotSpotAdminForm, HotSpotServiceRuleAdminForm

class InlineHotSpotTagAdmin(admin.TabularInline):
    model = HotSpotTag
    extra = 1


class InlineHotSpotServiceRuleAdmin(admin.TabularInline):
    model = HotSpotServiceRule
    form = HotSpotServiceRuleAdminForm
    formset = MandatoryInlineFormset
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
    list_display = ["id", "name", "address"]
    exclude = ["geohash", "lat", "lon"]
    inlines = [InlineHotSpotTagAdmin, InlineHotSpotServiceRuleAdmin, InlineHotSpotCustomPriceRuleAdmin,
               InlineHotSpotTariffRuleAdmin]
    form = HotSpotAdminForm


class OrderInlineAdmin(admin.TabularInline):
    model = Order
    extra = 0
    fields = ["from_raw", "to_raw", "depart_time", "arrive_time"]

class RideComputationInlineAdmin(admin.TabularInline):
    model = RideComputation
    extra = 0


class RideComputationAdmin(admin.ModelAdmin):
    list_display = ["id", "completed", "set_name"]
    inlines = [OrderInlineAdmin,]
    
    def set_name(self, obj):
        return '<a href="%s/%d">%s</a>' % ('/admin/sharing/ridecomputationset', obj.set.id, obj.set.name) if obj.set else ""
    set_name.allow_tags = True


class RideComputationSetAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "statistics"]
    inlines = [RideComputationInlineAdmin]

    def statistics(self, obj):
        return '<a href="%s">%s</a>' % (
            reverse('sharing.staff_controller.ride_computation_stat', kwargs={'computation_set_id': obj.id}),_("View"))

    statistics.allow_tags = True

class ProducerPassengerInlineAdmin(admin.TabularInline):
    model = ProducerPassenger
    fields = ["name", "phone", "is_sharing", "address"]
    extra = 0
    
class ProducerAdmin(admin.ModelAdmin):
    inlines = [ProducerPassengerInlineAdmin]

admin.site.register(HotSpot, HotSpotAdmin)
admin.site.register(Producer, ProducerAdmin)
admin.site.register(RideComputation, RideComputationAdmin)
admin.site.register(RideComputationSet, RideComputationSetAdmin)