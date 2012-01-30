from billing.models import BillingTransaction, BillingInfo
from django.contrib import admin

def disable(modeladmin, request, queryset):
    for billing_trx in queryset:
        billing_trx.disable()
disable.short_description = "Disable"

def enable(modeladmin, request, queryset):
    for billing_trx in queryset:
        billing_trx.enable()
enable.short_description = "Enable"

class BillingTransactionAdmin(admin.ModelAdmin):
    list_display = ["id", "dn_passenger_name", "dn_pickup_time", "dn_pickup", "dn_dropoff", "amount", "charge_date", "status", "debug", "invoice_sent", "comments", "transaction_id"]
    list_filter = ["status", "debug", "invoice_sent"]
    exclude = ["passenger", "order"]
    actions = [disable, enable]

    # prevent deletion via admin
    def get_actions(self, request):
        actions = super(BillingTransactionAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions
    def has_delete_permission(self, request, obj=None):
        return False

admin.site.register(BillingTransaction, BillingTransactionAdmin)