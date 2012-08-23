import simplejson
from ordering.models import StopType
from sharing.algo_api import AlgoField
from ordering.models import NEW_ORDER_ID

def create_algo_ride(ride):
    ride_points = []
    for order in ride.orders.all():
        ride_points.append(create_algo_point(StopType.PICKUP, [order.id], 0, order.from_lat, order.from_lon, order.from_raw))
        ride_points.append(create_algo_point(StopType.DROPOFF, [order.id], 0, order.to_lat, order.to_lon, order.to_raw))

    ride = {
        AlgoField.RIDE_ID: ride.id,
        AlgoField.ORDER_INFOS: dict([(str(order.id), create_order_info()) for order in ride.orders.all()]),
        AlgoField.RIDE_POINTS: ride_points,
    }
    return ride


def create_private_ride(order_settings):
    pickup = create_algo_point(StopType.PICKUP, [NEW_ORDER_ID], 0, order_settings.pickup_address.lat,
                               order_settings.pickup_address.lng, order_settings.pickup_address.formatted_address)
    dropoff = create_algo_point(StopType.DROPOFF, [NEW_ORDER_ID], 0, order_settings.dropoff_address.lat,
                                order_settings.dropoff_address.lng, order_settings.dropoff_address.formatted_address)

    ride = {
#        "m_RideID": ride.id,
        AlgoField.ORDER_INFOS: {str(NEW_ORDER_ID): create_order_info(price=44)},
        AlgoField.RIDE_POINTS: [pickup, dropoff],
    }
    return ride


def create_order_info(price=37.925):
    return {
        AlgoField.PRICE_SHARING: price
    }


def create_algo_point(stoptype, order_ids, offset_time, lat, lng, address):
    order_ids = [long(id) for id in order_ids]
    return {
        AlgoField.ORDER_IDS: order_ids,
        AlgoField.OFFSET_TIME: offset_time,
        AlgoField.POINT_ADDRESS: {
            AlgoField.LAT: lat,
            AlgoField.LNG: lng,
            AlgoField.NAME: address
        },
        AlgoField.TYPE: AlgoField.PICKUP if stoptype == StopType.PICKUP else AlgoField.DROPOFF
    }


def add_order_to_ride(algo_ride, order_settings):
    order_info = create_order_info()
    algo_ride[AlgoField.ORDER_INFOS][NEW_ORDER_ID] = order_info

    pickup = create_algo_point(StopType.PICKUP, [NEW_ORDER_ID], 0, order_settings.pickup_address.lat,
                               order_settings.pickup_address.lng, order_settings.pickup_address.formatted_address)
    dropoff = create_algo_point(StopType.DROPOFF, [NEW_ORDER_ID], 0, order_settings.dropoff_address.lat,
                                order_settings.dropoff_address.lng, order_settings.dropoff_address.formatted_address)
    algo_ride[AlgoField.RIDE_POINTS].extend([pickup, dropoff])
    return algo_ride


def find_matches(candidate_rides, order_settings):
    response = []

    for ride in candidate_rides[:len(candidate_rides) / 2]:
        algo_ride = create_algo_ride(ride)
        add_order_to_ride(algo_ride, order_settings)
        response.append(algo_ride)

    private_ride = create_private_ride(order_settings)
    response.append(private_ride)
    return simplejson.dumps(response)