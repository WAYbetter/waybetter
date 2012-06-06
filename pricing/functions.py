import logging
import random

HANDLING_FEE = 2 # NIS
MAX_DISCOUNT_FACTOR = 0.6 # the discount for 100% popularity
TWO_SEATS_PRICE_FACTOR = 0.4 # add this to the delta between base_price and popularity price

def get_base_sharing_price(cost):
#    return 0.59 * cost
    return cost + HANDLING_FEE


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
    logging.info("adding noise: noises[%s] --> noise[%s] * limit[%s] = (1+%s) * number[%s] = %s" %
                 (",".join([str(n) for n in noises]), noise, signed_limit, noise * signed_limit, number,
                  noisy_number))

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

