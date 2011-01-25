# -*- coding: utf-8 -*-
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse

from common.models import City, Country

from ordering.models import Passenger, Order, WorkStation, Station, OrderAssignment
from ordering.forms import OrderForm
from ordering.dispatcher import assign_order
from ordering.order_manager import NO_MATCHING_WORKSTATIONS_FOUND, ORDER_HANDLED
from ordering.station_connection_manager import set_heartbeat
from ordering.decorators import passenger_required, passenger_required_no_redirect, NOT_A_USER, NOT_A_PASSENGER, CURRENT_PASSENGER_KEY
from ordering.pricing import estimate_cost, IsraelExtraCosts, CostType, TARIFF1_START, TARIFF2_START
from ordering.testing.meter_calculator import calculate_tariff1, calculate_tariff2

from util import setup_testing_env
import logging
import datetime

PASSENGER = None
ORDER = None
ORDER_DATA = {}

def create_test_order():
    global ORDER
    global ORDER_DATA

    ORDER_DATA = {
        "from_city": u'1604',
        "from_country": u'12',
        "from_geohash": u'swnvcbg7d23u',
        "from_lat": u'32.073654',
        "from_lon": u'34.765465',
        "from_raw": u'אלנבי 1, תל אביב יפו',
        "from_street_address": u'אלנבי',
        "geocoded_from_raw": u'אלנבי 1, תל אביב יפו',
        "to_city": u'1604',
        "to_country": u'12',
        "to_geohash": u'swnvcbdruxgz',
        "to_lat": u'32.07238',
        "to_lon": u'34.764862',
        "to_raw": u'גאולה 1, תל אביב יפו',
        "to_street_address": u'גאולה',
        "geocoded_to_raw": u'גאולה 1, תל אביב יפו',
        # junk field
        "foo": "bar",
    }

    form = OrderForm(data=ORDER_DATA, passenger=PASSENGER)
    order = form.save()
    order.passenger = PASSENGER
    order.save()
    ORDER = order

def create_passenger():
    global PASSENGER

    test_user = User.objects.get(username='test_user')
    passenger = Passenger()
    passenger.user = test_user
    passenger.country = Country.objects.filter(code="IL").get()
    passenger.save()
    PASSENGER = passenger

def resuscitate_work_stations():
    for ws in WorkStation.objects.all():
        set_heartbeat(ws)


#
# testing starts here
#

class OrderingTest(TestCase):

    fixtures = ['countries.yaml', 'cities.yaml', 'ordering_test_data.yaml']

    def setUp(self):
        setup_testing_env.setup_appengine_task_queue()

        self.test_user = User.objects.get(username='test_user')
        self.passenger = Passenger.objects.filter(user=self.test_user)


    def test_login(self):
        login = self.client.login(username='test_user', password='wrong_password')
        self.assertFalse(login)
        login = self.client.login(username='test_user', password='test_user')
        self.assertTrue(login)

    def test_show_passenger_home(self):
        response = self.client.get(reverse('ordering.passenger_controller.passenger_home'))
        self.assertEqual(response.status_code, 200)

    def test_allow_book_order(self):
        # not logged in, forbidden
        response = self.client.post(reverse('ordering.passenger_controller.book_order'))
        self.assertTrue((response.content, response.status_code) == (NOT_A_PASSENGER, 403))

        # login in with no passenger, forbidden
        self.client.login(username='test_user_no_passenger', password='test_user_no_passenger')
        response = self.client.post(reverse('ordering.passenger_controller.book_order'))
        self.assertTrue((response.content, response.status_code) == (NOT_A_PASSENGER, 403))
        self.client.logout()

        # login in with passenger, should be OK
        create_passenger()

        self.client.login(username='test_user', password='test_user')
        response = self.client.post(reverse('ordering.passenger_controller.book_order'))
        self.assertTrue(response.status_code == 200)
        self.client.logout()

    def test_required_fields(self):
        order_form = OrderForm()
        required_fields = []
        for field_name in order_form.fields:
            if order_form.fields.get(field_name).required:
                required_fields.append(field_name)

        REQUIRED_FIELDS = ["from_city", "from_country", "from_geohash", "from_lat", "from_lon", "from_raw",
                           "from_street_address", "geocoded_from_raw", "to_city", "to_country", "to_geohash", "to_lat",
                           "to_lon", "to_raw", "to_street_address", "geocoded_to_raw", ]

        self.assertTrue(REQUIRED_FIELDS.sort() == required_fields.sort(), "A required form field is missing or was added.")

    def test_form_validation(self):
        bad_data = {
            "cross country order": {"from_country": u"1248"},
            "same country but no service": {"from_country": u"1248", "to_country": u"1248"},
            "no station in valid distance": {"from_lat": 33.239736, "from_lon": 35.654583, "to_lat": 29.550283, "to_lon": 34.914551},
        }

        create_passenger()
        create_test_order()

        # good order
        form = OrderForm(data=ORDER_DATA, passenger=PASSENGER)
        self.assertTrue(form.is_valid(), "Form should pass validation.")

        # bad orders
        for dict_name in bad_data:
            bad_order = ORDER_DATA.copy()
            bad_order.update(bad_data[dict_name])
            form = OrderForm(data=bad_order, passenger=PASSENGER)
            self.assertFalse(form.is_valid(), "Form should fail validation: %s" % dict_name)

class OrderManagerTest(TestCase):
    """Unit test for the logic of the order manager."""

    fixtures = ['countries.yaml', 'cities.yaml', 'stations_data.yaml']

    def setUp(self):
        setup_testing_env.setup_appengine_task_queue()
        create_test_users()
        create_test_order()

    def test_book_order(self):
        # the call made by book_order_async
        response = self.client.post(reverse('ordering.order_manager.book_order'), data={"order_id": ORDER.id})

        # working stations are dead, assignment should fail
        self.assertTrue((response.content, response.status_code) == (NO_MATCHING_WORKSTATIONS_FOUND, 200), "Assignment should fail: workstations are dead")

        # resuscitate all work stations and try again
        resuscitate_work_stations()
        response = self.client.post(reverse('ordering.order_manager.book_order'), data={"order_id": ORDER.id})
        self.assertTrue((response.content, response.status_code) == (ORDER_HANDLED, 200), "Assignment should succeed: workstations are live")

    def test_redispatch_ignored_orders(self):
        order = ORDER
        order.assignments.all().delete()
        order_assignment = OrderAssignment()
        response = self.client.post(reverse('ordering.order_manager.redispatch_ignored_orders'), data={"order_id": ORDER.id})


#
#
#    def test_dispatcher(self):
#        """Test the ordering logic of the dispatcher."""
#
#        # resuscitate work stations
#        for ws in WorkStation.objects.all():
#            set_heartbeat(ws)
#
#        # test default station
#        default_station = Station.objects.get(name="teststation2")
#        self.passenger.default_station = default_station
#        self.passenger.save()
#
#        order_assignment = assign_order(self.order)
#        self.assertTrue(order_assignment.station == default_station)
#        self.assertTrue(True)



#
#
#    def test_get_order_history(self):
#
#        self.login()
#
#        response = self.client.get(reverse('ordering.passenger_controller.get_orders_data'))
#        self.assertEqual(response.status_code, 200)
#        data = simplejson.loads(response.content)
#        self.assertEqual(11, len(data))


class PricingTest(TestCase):
    """
    Unit test for pricing algorithm.
    """
    fixtures = ['countries.yaml', 'cities.yaml', 'rules.json']

    def test_estimate_cost(self):

        # init Israel test
        IL = Country.objects.filter(code="IL").get()
        city_a = City.objects.get(name="תל אביב יפו")
        city_b = City.objects.get(name="אור יהודה")
        phone_order_price = IL.extra_charge_rules.get(rule_name=IsraelExtraCosts.PHONE_ORDER).cost
        t, d = 768, 4110

        logging.info("\nTesting cost estimation, with estimated duration: %d & estimated distance: %d" % (t, d))

        #
        # meter tests
        #
        expected_type = CostType.METER

        # tariff 1 test
        expected_cost = calculate_tariff1(t, d) + phone_order_price

        cost, type = estimate_cost(t, d, IL.code, time=datetime.time(05, 30, 00))
        logging.info("tariff 1 estimation: %d (expected %d)" % (cost, expected_cost))
        self.assertEqual((cost, type), (expected_cost, expected_type), "Cost calculation yielded wrong result")

        cost, type = estimate_cost(t, d, IL.code, time=datetime.time(21, 00, 00))
        logging.info("tariff 1 estimation: %d (expected %d)" % (cost, expected_cost))
        self.assertEqual((cost, type), (expected_cost, expected_type), "Cost calculation yielded wrong result")

        # tariff2 test
        expected_cost = calculate_tariff2(t, d) + phone_order_price

        cost, type = estimate_cost(t, d, IL.code, time=datetime.time(21, 00, 1))
        logging.info("tariff 2 estimation: %d (expected %d)" % (cost, expected_cost))
        self.assertEqual((cost, type), (expected_cost, expected_type), "Cost calculation yielded wrong result")

        cost, type = estimate_cost(t, d, IL.code, time=datetime.time(05, 29, 59))
        logging.info("tariff 2 estimation: %d (expected %d)" % (cost, expected_cost))
        self.assertEqual((cost, type), (expected_cost, expected_type), "Cost calculation yielded wrong result")

        # weekend test
        expected_cost = calculate_tariff2(t, d) + phone_order_price

        cost, type = estimate_cost(t, d, IL.code, day=7, time=datetime.time(23, 59, 59))
        logging.info("weekend estimation: %d (expected %d)" % (cost, expected_cost))
        self.assertEqual((cost, type), (expected_cost, expected_type), "Cost calculation yielded wrong result")

        # extras test
        extras = [IsraelExtraCosts.NATBAG_AIRPORT, IsraelExtraCosts.KVISH_6, IsraelExtraCosts.PHONE_ORDER]
        extras_cost = sum([IL.extra_charge_rules.get(rule_name=extra).cost for extra in extras])

        expected_cost = calculate_tariff1(t, d) + extras_cost # phone order is automatically added to extras list
        cost, type = estimate_cost(t, d, IL.code, time=datetime.time(12, 00), extras=extras)
        logging.info("tariff 1 + extras' estimation: %d (expected %d)" % (cost, expected_cost))
        self.assertEqual((cost, type), (expected_cost, expected_type), "Cost calculation yielded wrong result")

        expected_cost = calculate_tariff2(t, d) + extras_cost # phone order is automatically added to extras list
        cost, type = estimate_cost(t, d, IL.code, time=datetime.time(22, 00), extras=extras )
        logging.info("tariff 2 + extras' estimation: %d (expected %d)" % (cost, expected_cost))
        self.assertEqual((cost, type), (expected_cost, expected_type), "Cost calculation yielded wrong result")

        #
        # flat rate tests
        #
        expected_type = CostType.FLAT

        flat_rate_rules = IL.flat_rate_rules.filter(city1=city_a,city2=city_b)
        if not flat_rate_rules:
            flat_rate_rules = IL.flat_rate_rules.filter(city1=city_b,city2=city_a)

        self.assertTrue(flat_rate_rules, "No flat rate rule found between cities %s, %s" % (city_a.name,city_b.name))

        logging.info("\nTesting flat rate prices, with cities: %s , %s" % (city_a.name, city_b.name))

        for rule in flat_rate_rules:
            # tariff 1 test
            if rule.from_day == 1 and rule.from_hour == TARIFF1_START:
                expected_cost = rule.fixed_cost + phone_order_price
                cost, type = estimate_cost(t, d, IL.code, time=datetime.time(12, 00), cities=[city_a.id, city_b.id])
                logging.info("flat rate tariff1 test: %d (expected %d)" % (cost, expected_cost))
                self.assertEqual((cost, type), (expected_cost, expected_type), "Cost calculation yielded wrong result")

            # tariff 2 test
            if rule.from_day == 1 and rule.from_hour == TARIFF2_START:
                expected_cost = rule.fixed_cost + phone_order_price
                cost, type = estimate_cost(t, d, IL.code, time=datetime.time(21, 30), cities=[city_a.id, city_b.id])
                logging.info("flat rate tariff 2 test: %d (expected %d)" % (cost, expected_cost))
                self.assertEqual((cost, type), (expected_cost, expected_type), "Cost calculation yielded wrong result")

            # weekend test
            if rule.from_day == 7:
                expected_cost = rule.fixed_cost + phone_order_price
                cost, type = estimate_cost(t, d, IL.code, cities=[city_a.id, city_b.id], day=7)
                logging.info("flat rate weekend test: %d (expected %d)" % (cost, expected_cost))
                self.assertEqual((cost, type), (expected_cost, expected_type), "Cost calculation yielded wrong result")
