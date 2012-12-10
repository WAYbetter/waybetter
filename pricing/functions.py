import logging
from pricing.models import DiscountRule

def get_discount_rules_and_dt(order_settings, start_dt, end_dt, delta):
    active_discounts = []
    pickup_dt = order_settings.pickup_dt

    for discount_rule in DiscountRule.objects.all():
        active_dt = None
        if discount_rule.is_active_at(pickup_dt, order_settings.pickup_address, order_settings.dropoff_address): # we have an exact match for this pickup_dt
            active_dt = pickup_dt

        else: # no exact match found for this rule, search for next best
            first_active_dt = discount_rule.get_closest_active(pickup_dt, start_dt, end_dt, delta)
            if first_active_dt and discount_rule.is_active_at(first_active_dt, order_settings.pickup_address, order_settings.dropoff_address):
                active_dt = first_active_dt

        if active_dt:
            active_discounts.append((discount_rule, active_dt))

    logging.info("active discounts: %s" % active_discounts)
    return active_discounts