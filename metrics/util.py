import logging

def sort_by_metrics(objects, metrics, **kwargs):
    total = compute_metrics(objects, metrics, **kwargs)
    return sorted(objects, key=lambda obj: total[obj], reverse=True)

def compute_metrics(objects, metrics, **kwargs):
    total = dict([(obj, 0) for obj in objects])

    for metric in metrics:
        try:
            result = metric.compute(objects, **kwargs)
            for obj in result.keys():
                total[obj] += result[obj] * metric.weight

        except Exception, e:
            logging.error("error computing metric %s: %s" % (metric, e))

    log = ""
    for key in total.keys():
        log += "%s: %f\n" % (key, total[key])

    logging.info("metrics total:\n%s" % log)
    return total
