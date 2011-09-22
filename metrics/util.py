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

            result_log = u"Results for %s (DESC):" % metric.name
            for t in sorted(result.items(), key = lambda tup: tup[1], reverse=True):
                result_log += u"\n%s: %f" % t
            logging.info(result_log)

        except Exception, e:
            logging.error("error computing metric %s: %s" % (metric, e))

    log = u"Metrics total (DESC):"
    for t in sorted(total.items(), key = lambda tup: tup[1], reverse=True):
        log += u"\n%s: %f" % t
    logging.info(log)
    
    return total
