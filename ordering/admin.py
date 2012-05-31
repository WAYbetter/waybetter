from google.appengine.api.taskqueue import taskqueue
from billing.enums import BillingStatus
from common.util import blob_to_image_tag
from django.contrib import admin, messages
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _
from django.forms.models import BaseInlineFormSet
from ordering.models import Passenger, Order, OrderAssignment, Station, WorkStation, Phone, MeteredRateRule, FlatRateRule, Feedback, Business, SharedRide, RidePoint, Driver, Taxi, TaxiDriverRelation, StationFixedPriceRule, CHARGED, CANCELLED, Device, InstalledApp, RideComputation, RideComputationSet
import station_connection_manager
from common.models import Country
from common.forms import MandatoryInlineFormset
from sharing.sharing_dispatcher import dispatch_ride
from sharing.station_controller import show_ride, send_ride_voucher
import forms


class OrderInlineAdmin(admin.TabularInline):
    model = Order
    extra = 0
    fields = ["from_raw", "to_raw", "depart_time", "arrive_time", "passenger", "status"]

class OrderAdmin(admin.ModelAdmin):
    def cancel_order(modeladmin, request, queryset):
        for order in queryset:
            if order.status == CHARGED:
                messages.error(request, "%s: order was already charged" % order.id)
            else:
                for tx in order.billing_transactions.all():
                    if tx.status == BillingStatus.CHARGED:
                        messages.error(request, "%s: billing already charged" % order.id)
                        break

                    tx.disable()

                else: # no charged transactions, cancel order
                    order.change_status(new_status=CANCELLED)
                    messages.info(request, "%s: order cancelled" % order.id)

    cancel_order.short_description = _("Cancel")

    list_display = ["create_date", "from_raw", "to_raw", "debug", "station_name", "status", "pickup_time", "passenger", "passenger_rating"]
    list_filter = ["status", "station"]
    ordering = ['-create_date']
    actions = [cancel_order]

    def station_name(self, obj):
        if obj.station:
            return obj.station.get_admin_link()

    station_name.allow_tags = True

class SharedRideAdmin(admin.ModelAdmin):
    inlines = [OrderInlineAdmin,]
    list_display = ["id", "create_date", "debug", "num_orders", "computation_id", "depart_time", "arrive_time", "status", "map", "station", "taxi_number", "driver_name"]

    def num_orders(self, obj):
        return obj.orders.count()

    def computation_id(self, obj):
        return obj.computation.id

    def driver_name(self, obj):
        return obj.driver.name

    def taxi_number(self, obj):
        return obj.taxi.number

    def map(self, obj):
        return '<a href="%s">map</a>' % reverse(show_ride, args=[obj.id])
    map.allow_tags = True

    actions = ['dispatch', 'resend_voucher']

    def dispatch(self, request, queryset):
        dispatched = []
        not_dispatched = []

        for ride in queryset:
            if ride.station:
                not_dispatched.append(ride)
            else:
                dispatch_ride(ride)
                dispatched.append(ride)

        if not_dispatched:
            messages.error(request, "%s rides not dispatched, already assigned to station %s" % (len(not_dispatched), [ride.id for ride in not_dispatched]))
        if dispatched:
            messages.error(request, "%s rides dispatched %s" % (len(dispatched), [ride.id for ride in dispatched]))
    dispatch.short_description = _("Dispatch ride")

    def resend_voucher(self, request, queryset):
        sent = []
        for ride in queryset:
            if ride.station.vouchers_emails:
                q = taskqueue.Queue('ride-notifications')
                task = taskqueue.Task(url=reverse(send_ride_voucher), params={"ride_id": ride.id})
                q.add(task)
                sent.append(ride)
        if sent:
            messages.info(request, "%d vouchers sent %s" % (len(sent), [ride.station.vouchers_emails for ride in sent]))
        else:
            messages.info(request, "Nothing sent")
    resend_voucher.short_description = _("Resend Voucher")

class RidePointAdmin(admin.ModelAdmin):
    list_display = ["id", "create_date", "stop_time", "type", "address", "ride_id"]

    def ride_id(self, obj):
        return obj.ride_id

class RideComputationAdmin(admin.ModelAdmin):
    def send_computation(modeladmin, request, queryset):
        from sharing.algo_api import submit_computations
        from datetime import datetime

        for ride_computation in queryset:
            submit_computations(ride_computation.key, datetime.now())

        messages.info(request, "sent to algo: %s" % ",".join([str(rc.id) for rc in queryset]))

    send_computation.short_description = "Send computation to algo"

    list_display = ["create_date", "id", "debug", "status", "num_orders", "key", "algo_key", "set_name"]
    inlines = [OrderInlineAdmin,]
    actions = [send_computation]

    def num_orders(self, obj):
        return obj.orders.count()

    def set_name(self, obj):
        return '<a href="%s">%s</a>' % (reverse('sharing.staff_controller.ride_computation_stat', kwargs={'computation_set_id': obj.set.id}), obj.set.name)
    set_name.allow_tags = True

class RideComputationInlineAdmin(admin.TabularInline):
    model = RideComputation
    extra = 0

class RideComputationSetAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "statistics"]
    inlines = [RideComputationInlineAdmin]

    def statistics(self, obj):
        return '<a href="%s">%s</a>' % (reverse('sharing.staff_controller.ride_computation_stat', kwargs={'computation_set_id': obj.id}),_("View"))

    statistics.allow_tags = True


class TaxiAdmin(admin.ModelAdmin):
    list_display = ["id", "dn_station_name", "number"]
    exclude = ["dn_station_name"]


class DriverAdmin(admin.ModelAdmin):
    list_display = ["id", "dn_station_name", "name"]
    exclude = ["dn_station_name"]


class TaxiDriverRelationAdmin(admin.ModelAdmin):
    list_display = ["id", "_driver", "_taxi", "dn_station_name"]
    list_filter = ["driver", "taxi"]
    exclude = ["dn_station_name"]

    def _driver(self, obj):
        driver = Driver.by_id(obj.driver_id)
        return driver

    def _taxi(self, obj):
        return Taxi.by_id(obj.taxi_id)


class PassengerAdmin(admin.ModelAdmin):
    list_display = ["id", "user_name", "phone"]

    def user_name(self, obj):
        if obj.user:
            return '<a href="%s/%d">%s</a>' % ('/admin/auth/user', obj.user.id, obj.user.username)
        else:
            return "-- No User -- "

    user_name.allow_tags = True

def send_welcome_email(modeladmin, request, queryset):
    for business in queryset:
        business.send_welcome_email(chosen_password="*****")

send_welcome_email.short_description = "Send welcome email"

class BusinessAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "contact_person"]
    actions = [send_welcome_email]


class PhoneAdmin(admin.TabularInline):
    model = Phone
    formset = MandatoryInlineFormset
    extra = 2

class StationFixedPriceRuleAdmin(admin.TabularInline):
    model = StationFixedPriceRule
    extra = 1

def build_workstations(modeladmin, request, queryset):
    for station in queryset:
        station.delete_workstations()
        station.build_workstations()

build_workstations.short_description = "Build workstations"

class StationAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "logo_img"]
    inlines = [PhoneAdmin, StationFixedPriceRuleAdmin]
    exclude = ["geohash", "lat", "lon", "number_of_ratings", "average_rating", "last_assignment_date"]
    form = forms.StationAdminForm
    actions = [build_workstations]

    def logo_img(self, obj):
        res = ""
        if obj.logo:
            res = blob_to_image_tag(obj.logo, height=50)

        if not res:
            res = _("No Logo")

        return res

    logo_img.allow_tags = True


class OrderAssignmentAdmin(admin.ModelAdmin):
    list_display = ["create_date", "station_name", "work_station_name", "order_details", "status"]
    list_filter = ["status", "work_station", "station"]
    ordering = ['-create_date']

    def station_name(self, obj):
        return obj.station.get_admin_link()

    station_name.allow_tags = True

    def work_station_name(self, obj):
        return obj.work_station.get_admin_link()

    work_station_name.allow_tags = True

    def order_details(self, obj):
        return unicode(obj.order)


def build_installer(modeladmin, request, queryset):
    count = 0
    for ws in queryset:
        ws.build_installer()
        count += 1
    modeladmin.message_user(request, _("%d installers built") % count)

build_installer.short_description = _("Build Installer")

def build_sharing_installer(modeladmin, request, queryset):
    for ws in queryset:
        ws.build_sharing_installer()

build_sharing_installer.short_description = "Build Sharing Installer"

def check_connection(modeladmin, request, queryset):
    checks_performed = 0
    for ws in queryset:
        if station_connection_manager.is_workstation_available(ws):
            station_connection_manager.check_connection(ws)
            checks_performed += 1
    modeladmin.message_user(request, _("%d checks performed successfully") % checks_performed)
check_connection.short_description = _("Check Connection")

def send_dummy_order(modeladmin, request, queryset):
    orders_sent = 0
    for ws in queryset:
        if station_connection_manager.is_workstation_available(ws):
            station_connection_manager.push_dummy_order(ws)
            orders_sent += 1
    modeladmin.message_user(request, _("%d dummy orders sent") % orders_sent)
send_dummy_order.short_description = _("Send Dummy Order")

class WorkStationAdmin(admin.ModelAdmin):
    list_display = ["id", "work_station_user", "station_name", "is_online"]
    list_filter = ["is_online"]
    exclude = ["is_online", "last_assignment_date"]
    actions = [build_installer, build_sharing_installer, send_dummy_order, check_connection]

    def work_station_user(self, obj):
        return obj.get_admin_link()

    work_station_user.allow_tags = True

    def station_name(self, obj):
        return obj.station.get_admin_link()

    station_name.admin_order_field = 'dn_station_name'
    station_name.allow_tags = True

    def online_status(self, obj):
        if station_connection_manager.is_workstation_available(obj):
            return '<img src="%s">' % ("/static/images/online_small.gif")
        else:
            return ""

    online_status.allow_tags = True


class MeteredRateRuleAdmin(admin.TabularInline):
    model = MeteredRateRule
    extra = 5


class FlatRateRuleAdmin(admin.ModelAdmin):
    pass


class ExtraChargeRuleAdmin(admin.ModelAdmin):
    pass


class CountryPricingRulesAdmin(admin.ModelAdmin):
    inlines = [MeteredRateRuleAdmin, ]


class FeedbackAdmin(admin.ModelAdmin):
    model = Feedback
    list_display = ["feedback"]
    list_filter = Feedback.field_names()

    def feedback(self, obj):
        return unicode(obj)

    feedback.allow_tags = True

class InstalledAppAdmin(admin.ModelAdmin):
    list_display = ["name", "blocked", "passenger"]

admin.site.register(SharedRide, SharedRideAdmin)
admin.site.register(RidePoint, RidePointAdmin)
admin.site.register(RideComputation, RideComputationAdmin)
admin.site.register(RideComputationSet, RideComputationSetAdmin)
admin.site.register(Taxi, TaxiAdmin)
admin.site.register(Driver, DriverAdmin)
admin.site.register(TaxiDriverRelation, TaxiDriverRelationAdmin)
admin.site.register(Passenger, PassengerAdmin)
admin.site.register(Business, BusinessAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(OrderAssignment, OrderAssignmentAdmin)
admin.site.register(Station, StationAdmin)
admin.site.register(WorkStation, WorkStationAdmin)
admin.site.register(Country, CountryPricingRulesAdmin)
admin.site.register(FlatRateRule, FlatRateRuleAdmin)
admin.site.register(Feedback, FeedbackAdmin)
admin.site.register(InstalledApp, InstalledAppAdmin)
