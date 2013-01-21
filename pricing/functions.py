import logging
from ordering.models import PromoCodeActivation
from pricing.data_objects import DiscountData
from pricing.models import DiscountRule

def compute_discounts_data(order_settings, start_dt, end_dt, delta, user=None):
    """

    @param order_settings:
    @param start_dt:
    @param end_dt:
    @param delta:
    @param user:
    @return: a list of DiscountData objects
    """
    passenger = None
    user_email_domain = None
    if user:
        user_email_domain = user.email.split("@")[1]
        passenger = user.passenger


    logging.info("get discounts  @%s" % user_email_domain)

    discounts_data = []

    for discount_rule in DiscountRule.objects.filter(open_to_all=True):
        if discount_rule.email_domains and (user_email_domain not in discount_rule.email_domains):
            logging.info(u"skipping: %s - only for %s" % (discount_rule.name, ", ".join(discount_rule.email_domains)))
            continue

        active_dt = get_active_dt(discount_rule, order_settings, start_dt, end_dt, delta)
        if active_dt:
            discounts_data.append(DiscountData(active_dt, discount_rule))

    if passenger:
        promo_activations = PromoCodeActivation.objects.filter(passenger=passenger, consumed=False)
        seen_promo_discounts = []

        for promo_code in [activation.promo_code for activation in promo_activations]:
            promotion = promo_code.promotion
            promo_discount_rule = promotion.discount_rule

            if promo_discount_rule in seen_promo_discounts:
                continue

            seen_promo_discounts.append(promo_discount_rule)
            active_dt = get_active_dt(promo_discount_rule, order_settings, start_dt, end_dt, delta)
            if active_dt:
                discounts_data.append(DiscountData(active_dt, promo_discount_rule, promotion=promotion, promo_code=promo_code))

    logging.info("active discounts: %s" % discounts_data)
    return discounts_data


def get_active_dt(discount_rule, order_settings, start_dt, end_dt, delta):
    pickup_dt = order_settings.pickup_dt

    active_dt = None
    if discount_rule.is_active_at(pickup_dt, order_settings.pickup_address, order_settings.dropoff_address): # we have an exact match for this pickup_dt
        active_dt = pickup_dt

    else: # no exact match found for this rule, search for next best
        first_active_dt = discount_rule.get_closest_active(pickup_dt, start_dt, end_dt, delta)
        if first_active_dt and discount_rule.is_active_at(first_active_dt, order_settings.pickup_address, order_settings.dropoff_address):
            active_dt = first_active_dt

    return active_dt