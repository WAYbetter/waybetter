import logging
import random
from common.util import convert_python_weekday
from pricing.models import DiscountRule

HANDLING_FEE = 2 # NIS
MAX_DISCOUNT_FACTOR = 0.6 # the discount for 100% popularity
TWO_SEATS_PRICE_FACTOR = 0.4 # add this to the delta between base_price and popularity price

#def get_base_sharing_price(cost):
#   return cost + HANDLING_FEE

def compute_discount(order_settings, price):
    for discount_rule in DiscountRule.objects.all():
        if discount_rule.is_active(order_settings.pickup_address.lat, order_settings.pickup_address.lng,
                                   order_settings.dropoff_address.lat, order_settings.dropoff_address.lng,
                                   order_settings.pickup_dt.date(), order_settings.pickup_dt.time()):

            return discount_rule.get_discount(price)

    return None


def get_base_sharing_price(start_lat, start_lon, end_lat, end_lon, d, t, estimated_distance=None, estimated_duration=None, meter_rules=None):
    from ordering.pricing import estimate_cost, CostType
    from sharing.algo_api import calculate_route

    if not (estimated_distance and estimated_duration):
        route_result = calculate_route(start_lat, start_lon, end_lat, end_lon)
        estimated_duration, estimated_distance = route_result["estimated_duration"], route_result["estimated_distance"]
        if estimated_duration == 0.0 and  estimated_distance == 0.0: # failed to calculate route
            return None

    
    estimated_cost, price_type = estimate_cost(estimated_duration, estimated_distance, day=convert_python_weekday(d.weekday()), time=t, meter_rules=meter_rules)
    assert price_type == CostType.METER

    return estimated_cost + HANDLING_FEE


def get_noisy_number_for_day_time(number, limit, day, t):
    """

    @param number:
    @param limit: floating point number in the range [0.0, 1.0]
    @param day: datetime.date
    @param t: datetime.time
    @return:
    """

    noises = [day.month / 12.0, day.weekday() / 6.0, t.hour / 24.0, t.minute / 60.0]
    noises = [round(n, 2) for n in noises]
    r = random.Random(t.hour + t.minute)
    sign = r.choice([-1, 1])

    return get_noisy_number(number, sign * limit, noises)


def get_noisy_number(number, signed_limit, noises):
    """

    @param number:
    @param signed_limit: floating point number in the range [-1.0, 1.0]
    @param noises: a list of floating point numbers in the range [0.0, 1.0]
    """
    non_zeros = len([s is not 0 for s in noises])
    noise = round(sum(noises) / non_zeros, 2)

    noisy_number = (1 + noise * signed_limit) * number
#    logging.info("adding noise: noises[%s] --> noise[%s] * limit[%s] = (1+%s) * number[%s] = %s" %
#                 (",".join([str(n) for n in noises]), noise, signed_limit, noise * signed_limit, number,
#                  noisy_number))

    return noisy_number


def get_popularity_price(popularity, base_price):
    """

    @param popularity: floating point number in the range [0.0, 1.0]
    @param base_price:
    @return:
    """
    popularity = round(popularity, 2)
    assert 0.0 <= popularity <= 1.0, "popularity must be in range [0.0, 1.0]"

    if not popularity:
        return base_price

    max_price = base_price
    min_price = (1 - MAX_DISCOUNT_FACTOR) * base_price

    new_price = max_price - (max_price - min_price) * popularity

    assert new_price <= base_price
    logging.info("computing popularity %s: base_price=%s, new price=%s, discount=%s NIS" %
                 (popularity, base_price, new_price, base_price - new_price))

    return new_price

