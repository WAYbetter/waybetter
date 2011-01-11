import datetime
## Calculate the correct price of the ride based on prices published by ministry of transportation

TARIFF1_START = datetime.time(05,30)
TARIFF1_END = datetime.time(21,00)
TARIFF2_START = datetime.time(21,01)
TARIFF2_END = datetime.time(05,29)

PHONE_ORDER = 4.5

#Tariff1
TARIFF1_BASE_PRICE = 11.1# in NIS
TARIFF1_BASE_TIME = 83 # in sec
TARIFF1_BASE_DISTANCE = 559.45 # in meter
TARIFF1_TICK_TIME_BELOW_15K = 12 # in sec
TARIFF1_TICK_DISTANCE_BELOW_15K = 90.09 # in meter
TARIFF1_TICK_COST_BELOW_15K = 0.3 # in NIS
TARIFF1_TICK_TIME_OVER_15K = 12 # in sec
TARIFF1_TICK_DISTANCE_OVER_15K = 75.14 # in meter
TARIFF1_TICK_COST_OVER_15K = 0.3 # in NIS

#TARIFF2
TARIFF2_BASE_PRICE = 11.1 # in NIS
TARIFF2_BASE_TIME = 36 # in sec
TARIFF2_BASE_DISTANCE = 153.81 # in meter
TARIFF2_TICK_TIME_BELOW_15K = 10 # in sec
TARIFF2_TICK_DISTANCE_BELOW_15K = 72.15 # in meter
TARIFF2_TICK_COST_BELOW_15K = 0.3 # in NIS
TARIFF2_TICK_TIME_OVER_15K = 10 # in sec
TARIFF2_TICK_DISTANCE_OVER_15K = 60.03 # in meter
TARIFF2_TICK_COST_OVER_15K = 0.3 # in NIS

#Tariff1 Eilat
TARIFF1_BASE_PRICE_EILAT = 9.5# in NIS
TARIFF1_BASE_TIME_EILAT = 83 # in sec
TARIFF1_BASE_DISTANCE_EILAT = 559.79 # in meter
TARIFF1_TICK_TIME_BELOW_15K_EILAT = 15 # in sec
TARIFF1_TICK_DISTANCE_BELOW_15K_EILAT = 105.52 # in meter
TARIFF1_TICK_COST_BELOW_15K_EILAT = 0.3 # in NIS
TARIFF1_TICK_TIME_OVER_15K_EILAT = 15 # in sec
TARIFF1_TICK_DISTANCE_OVER_15K_EILAT = 84.52 # in meter
TARIFF1_TICK_COST_OVER_15K_EILAT = 0.3 # in NIS

#TARIFF2 Eilat
TARIFF2_BASE_PRICE_EILAT = 9.5# in NIS
TARIFF2_BASE_TIME_EILAT = 36 # in sec
TARIFF2_BASE_DISTANCE_EILAT = 154.17 # in meter
TARIFF2_TICK_TIME_BELOW_15K_EILAT = 12 # in sec
TARIFF2_TICK_DISTANCE_BELOW_15K_EILAT = 84.42 # in meter
TARIFF2_TICK_COST_BELOW_15K_EILAT = 0.3 # in NIS
TARIFF2_TICK_TIME_OVER_15K_EILAT = 12 # in sec
TARIFF2_TICK_DISTANCE_OVER_15K_EILAT = 67.59 # in meter
TARIFF2_TICK_COST_OVER_15K_EILAT = 0.3 # in NIS


# main method
def calculate_meter(duration,distance,time,day):
    cost = 0

    if day==7:
        cost =  calculate_tariff2(duration,distance)
    elif TARIFF2_START <= time <= datetime.time(23,59,59):
        cost =  calculate_tariff2(duration,distance)
    elif datetime.time(00,00,00) <= time <= TARIFF2_END:
        cost =  calculate_tariff2(duration,distance)
    else:
        cost = calculate_tariff1(duration,distance)

    return cost + PHONE_ORDER  

# helper methods
def calculate_tariff1(duration, distance):
    extra_distance = 0
    if distance > 15000:
        extra_distance = distance - 15000
        distance = 15000

    if duration < TARIFF1_BASE_TIME or distance < TARIFF1_BASE_DISTANCE:
        return TARIFF1_BASE_PRICE

    #price up to 15K
    tick_cost_by_time = (duration - TARIFF1_BASE_TIME) / TARIFF1_TICK_TIME_BELOW_15K * TARIFF1_TICK_COST_BELOW_15K
    tick_cost_by_distance = (
                            distance - TARIFF1_BASE_DISTANCE) / TARIFF1_TICK_DISTANCE_BELOW_15K * TARIFF1_TICK_COST_BELOW_15K

    #price over 15K
    if extra_distance:
        ## This is not the absolutely correct price in case the distance is greater than 15K since there is no way to know how much time the first 15K took
        #tick_cost_by_time += extra_time / TARIFF1_TICK_TIME_OVER_15K * TARIFF1_TICK_COST_OVER_15K
        tick_cost_by_distance += extra_distance / TARIFF1_TICK_DISTANCE_OVER_15K * TARIFF1_TICK_COST_OVER_15K

    tick_cost = max(tick_cost_by_distance, tick_cost_by_time)
    return tick_cost + TARIFF1_BASE_PRICE

def calculate_tariff2(duration, distance):
    extra_distance = 0
    if distance > 15000:
        extra_distance = distance - 15000
        distance = 15000

    if duration < TARIFF2_BASE_TIME or distance < TARIFF2_BASE_DISTANCE:
        return TARIFF2_BASE_PRICE

    #price up to 15K
    tick_cost_by_time = (duration - TARIFF2_BASE_TIME) / TARIFF2_TICK_TIME_BELOW_15K * TARIFF2_TICK_COST_BELOW_15K
    tick_cost_by_distance = (
                            distance - TARIFF2_BASE_DISTANCE) / TARIFF2_TICK_DISTANCE_BELOW_15K * TARIFF2_TICK_COST_BELOW_15K

    #price over 15K
    if extra_distance:
        ## This is not the absolutely correct price in case the distance is greater than 15K since there is no way to know how much time the first 15K took
        #tick_cost_by_time += extra_time / TARIFF2_TICK_TIME_OVER_15K * TARIFF2_TICK_COST_OVER_15K
        tick_cost_by_distance += extra_distance / TARIFF2_TICK_DISTANCE_OVER_15K * TARIFF2_TICK_COST_OVER_15K

    tick_cost = max(tick_cost_by_distance, tick_cost_by_time)
    return tick_cost + TARIFF2_BASE_PRICE

def calculate_tariff1_eilat(duration, distance):
    extra_distance = 0
    if distance > 15000:
        extra_distance = distance - 15000
        distance = 15000

    if duration < TARIFF1_BASE_TIME_EILAT or distance < TARIFF1_BASE_DISTANCE_EILAT:
        return TARIFF1_BASE_PRICE_EILAT

    #price up to 15K
    tick_cost_by_time = (duration - TARIFF1_BASE_TIME_EILAT) / TARIFF1_TICK_TIME_BELOW_15K_EILAT * TARIFF1_TICK_COST_BELOW_15K_EILAT
    tick_cost_by_distance = (
                            distance - TARIFF1_BASE_DISTANCE_EILAT) / TARIFF1_TICK_DISTANCE_BELOW_15K_EILAT * TARIFF1_TICK_COST_BELOW_15K_EILAT

    #price over 15K
    if extra_distance:
        ## This is not the absolutely correct price in case the distance is greater than 15K since there is no way to know how much time the first 15K took
        #tick_cost_by_time += extra_time / TARIFF1_TICK_TIME_OVER_15K_EILAT * TARIFF1_TICK_COST_OVER_15K_EILAT
        tick_cost_by_distance += extra_distance / TARIFF1_TICK_DISTANCE_OVER_15K_EILAT * TARIFF1_TICK_COST_OVER_15K_EILAT

    tick_cost = max(tick_cost_by_distance, tick_cost_by_time)
    return tick_cost + TARIFF1_BASE_PRICE_EILAT

def calculate_tariff2_eilat(duration, distance):
    extra_distance = 0
    if distance > 15000:
        extra_distance = distance - 15000
        distance = 15000

    if duration < TARIFF2_BASE_TIME_EILAT or distance < TARIFF2_BASE_DISTANCE_EILAT:
        return TARIFF2_BASE_PRICE_EILAT

    #price up to 15K
    tick_cost_by_time = (duration - TARIFF2_BASE_TIME_EILAT) / TARIFF2_TICK_TIME_BELOW_15K_EILAT * TARIFF2_TICK_COST_BELOW_15K_EILAT
    tick_cost_by_distance = (
                            distance - TARIFF2_BASE_DISTANCE_EILAT) / TARIFF2_TICK_DISTANCE_BELOW_15K_EILAT * TARIFF2_TICK_COST_BELOW_15K_EILAT

    #price over 15K
    if extra_distance:
        ## This is not the absolutely correct price in case the distance is greater than 15K since there is no way to know how much time the first 15K took
        #tick_cost_by_time += extra_time / TARIFF2_TICK_TIME_OVER_15K_EILAT * TARIFF2_TICK_COST_OVER_15K_EILAT
        tick_cost_by_distance += extra_distance / TARIFF2_TICK_DISTANCE_OVER_15K_EILAT * TARIFF2_TICK_COST_OVER_15K_EILAT

    tick_cost = max(tick_cost_by_distance, tick_cost_by_time)
    return tick_cost + TARIFF2_BASE_PRICE_EILAT