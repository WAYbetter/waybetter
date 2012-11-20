from common.tz_support import TZ_INFO
from pricing.models import DiscountRule

def compute_discount(order_settings, price):
    for discount_rule in DiscountRule.objects.all():
        pickup_dt = order_settings.pickup_dt.astimezone(TZ_INFO["Asia/Jerusalem"])

        if discount_rule.is_active(order_settings.pickup_address.lat, order_settings.pickup_address.lng,
                                   order_settings.dropoff_address.lat, order_settings.dropoff_address.lng,
                                   pickup_dt.date(), pickup_dt.time()):

            return discount_rule.get_discount(price)

    return None
