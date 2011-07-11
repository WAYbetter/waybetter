from django.test import TestCase
from testing import setup_testing_env
from ordering.models import Station
from ordering.tests import create_test_order, FAR_AWAY_LON, FAR_AWAY_LAT
from models import ModelMetric, StationMetric
from util import compute_metrics
from errors import MetricError


def dummy_m1(objects, **kwargs):
    return dict([(obj, 1) for obj in objects])


def dummy_m2(objects, **kwargs):
    if kwargs.has_key('raise_error') and kwargs['raise_error']:
        raise MetricError()
    else:
        return dict([(obj, objects.index(obj) + 1) for obj in objects])


class BasicTests(TestCase):
    def test_compute_metrics(self):
        """
        Test sort_by_metrics using dummy metrics m1, m2.
        m1 (m2) gives higher rating to the first (second) object.
        """
        m1 = StationMetric(name="m1", weight=0.3, function_name="metrics.tests.dummy_m1")
        m1.save()
        m2 = ModelMetric(name="m2", weight=0.5, function_name="metrics.tests.dummy_m2")
        m1.save()

        o1 = "1st_object"
        o2 = "2nd_object"

        # compute m1, m2
        rating = compute_metrics([o1, o2], [m1, m2], as_dict=True)
        self.assertTrue(rating[o1] == 1 * 0.3 + 1 * 0.5 and rating[o2] == 1 * 0.3 + 2 * 0.5)

        # m2 raises error, should be skipped (only m1 is computed)
        rating = compute_metrics([o1, o2], [m1, m2], as_dict=True, raise_error=True)
        self.assertTrue(rating[o1] == rating[o2] == 1 * 0.3 + 0 * 0.5)


class StationMetricTests(TestCase):
    fixtures = ['station_metrics', 'countries', 'cities', 'ordering/fixtures/ordering_test_data.yaml']

    def setUp(self):
        setup_testing_env.setup()

        self.station1 = Station.objects.all()[0]
        self.station2 = Station.objects.all()[1]

    def test_internal_rating_metric(self):
        self.station1.internal_rating = 1
        self.station1.save()

        self.station2.internal_rating = 0
        self.station2.save()

        metric = StationMetric.objects.get(name='internal_rating_metric')
        rating = metric.compute([self.station1, self.station2])

        self.assertTrue(rating[self.station1] > rating[self.station2])

    def test_distance_to_pickup(self):
        order = create_test_order()

        self.station1.lat = order.from_lat
        self.station1.lon = order.from_lon
        self.station1.save()

        self.station2.lat = FAR_AWAY_LAT
        self.station2.lon = FAR_AWAY_LON
        self.station2.save()

        metric = StationMetric.objects.get(name='distance_from_pickup_metric')

        rating = metric.compute([self.station1, self.station2], order=order)
        self.assertTrue(rating[self.station1] > rating[self.station2])

        # if no order is given, raise exception
        self.assertRaises(MetricError, metric.compute, ([self.station1, self.station2]))





