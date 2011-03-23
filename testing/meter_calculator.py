## Calculate the correct price of the ride based on prices published by ministry of transportation

def calculate_tariff(duration, distance, tariff_dict):
    extra_distance = 0
    if distance > 15000:
        extra_distance = distance - 15000
        distance = 15000

    if duration < tariff_dict['BASE_TIME'] or distance < tariff_dict['BASE_DISTANCE']:
        return tariff_dict['BASE_PRICE']

    #price up to 15K
    tick_cost_by_time = (duration - tariff_dict['BASE_TIME']) / tariff_dict['TICK_TIME_BELOW_15K'] * tariff_dict['TICK_COST_BELOW_15K']
    tick_cost_by_distance = (
        distance - tariff_dict['BASE_DISTANCE']) / tariff_dict['TICK_DISTANCE_BELOW_15K'] * tariff_dict['TICK_COST_BELOW_15K']

    #price over 15K
    if extra_distance:
        ## This is not the absolutely correct price in case the distance is greater than 15K since there is no way to know how much time the first 15K took
        #tick_cost_by_time += extra_time / TICK_TIME_OVER_15K * TICK_COST_OVER_15K
        tick_cost_by_distance += extra_distance / tariff_dict['TICK_DISTANCE_OVER_15K'] * tariff_dict['TICK_COST_OVER_15K']

    tick_cost = max(tick_cost_by_distance, tick_cost_by_time)
    return tick_cost + tariff_dict['BASE_PRICE']
