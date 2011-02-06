import datetime
import ordering.pricing
## Calculate the correct price of the ride based on prices published by ministry of transportation

TARIFF1_START = ordering.pricing.TARIFF1_START
TARIFF1_END = ordering.pricing.TARIFF1_END
TARIFF2_START = ordering.pricing.TARIFF2_START
TARIFF2_END = ordering.pricing.TARIFF2_END

#TARIFF1
tariff1_dict = {
    'BASE_PRICE'              : 11.1, # in NIS
    'BASE_TIME'               : 83, # in sec
    'BASE_DISTANCE'           : 559.45, # in meter
    'TICK_TIME_BELOW_15K'     : 12, # in sec
    'TICK_DISTANCE_BELOW_15K' : 90.09, # in meter
    'TICK_COST_BELOW_15K'     : 0.3, # in NIS
    'TICK_TIME_OVER_15K'      : 12, # in sec
    'TICK_DISTANCE_OVER_15K'  : 75.14, # in meter
    'TICK_COST_OVER_15K'      : 0.3, # in NIS
    }

#TARIFF2
tariff2_dict = {
    'BASE_PRICE'              : 11.1, # in NIS
    'BASE_TIME'               : 36, # in sec
    'BASE_DISTANCE'           : 153.81, # in meter
    'TICK_TIME_BELOW_15K'     : 10, # in sec
    'TICK_DISTANCE_BELOW_15K' : 72.15, # in meter
    'TICK_COST_BELOW_15K'     : 0.3, # in NIS
    'TICK_TIME_OVER_15K'      : 10, # in sec
    'TICK_DISTANCE_OVER_15K'  : 60.03, # in meter
    'TICK_COST_OVER_15K'      : 0.3, # in NIS
    }

#Tariff1 Eilat
tariff1_eilat_dict = {
    'BASE_PRICE'              : 9.5, # in NIS
    'BASE_TIME'               : 83, # in sec
    'BASE_DISTANCE'           : 559.79, # in meter
    'TICK_TIME_BELOW_15K'     : 15, # in sec
    'TICK_DISTANCE_BELOW_15K' : 105.52, # in meter
    'TICK_COST_BELOW_15K'     : 0.3, # in NIS
    'TICK_TIME_OVER_15K'      : 15, # in sec
    'TICK_DISTANCE_OVER_15K'  : 84.52, # in meter
    'TICK_COST_OVER_15K'      : 0.3, # in NIS
    }

#TARIFF2 Eilat
tariff2_eilat_dict = {
    'BASE_PRICE'              : 9.5, # in NIS
    'BASE_TIME'               : 36, # in sec
    'BASE_DISTANCE'           : 154.17, # in meter
    'TICK_TIME_BELOW_15K'     : 12, # in sec
    'TICK_DISTANCE_BELOW_15K' : 84.42, # in meter
    'TICK_COST_BELOW_15K'     : 0.3, # in NIS
    'TICK_TIME_OVER_15K'      : 12, # in sec
    'TICK_DISTANCE_OVER_15K'  : 67.59, # in meter
    'TICK_COST_OVER_15K'      : 0.3, # in NIS
    }


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
