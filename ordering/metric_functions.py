from metrics.errors import MetricError
import logging

def internal_rating(stations, **kwargs):
    max_rating = 0.0
    log = ""

    for station in stations:
        internal_rating = station.internal_rating
        log += "%s: %d\n" % (station.name, internal_rating)

        if internal_rating > max_rating:
            max_rating = internal_rating

    logging.info("internal rating metric:\n%s" % log)
    return dict([(station, station.internal_rating / max_rating if max_rating else 0) for station in stations])


def internal_rating_ws(work_stations, **kwargs):
    station_rating = internal_rating([ws.station for ws in work_stations], **kwargs)
    return dict([(ws, station_rating[ws.station]) for ws in work_stations])


def distance_from_pickup(stations, **kwargs):
    if not kwargs.has_key('order'):
        raise MetricError("Must pass an order to compute distance_from_pickup metric")

    else:
        order = kwargs['order']

        d = {}
        max_distance = 0.0
        log = ""

        for station in stations:
            distance = float(station.distance_from_order(order=order, to_pickup=True, to_dropoff=False))
            log += "%s: %f\n" % (station.name, distance)

            if distance > max_distance:
                max_distance = distance

            d[station] = distance

        logging.info("distance from pickup metric:\n%s" % log)
        return dict([(station, 1 - d[station] / max_distance) for station in stations])

def distance_from_pickup_ws(work_stations, **kwargs):
    station_rating = distance_from_pickup([ws.station for ws in work_stations], **kwargs)
    return dict([(ws, station_rating[ws.station]) for ws in work_stations])
