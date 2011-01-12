# -*- coding: utf-8 -*-
from django.test import TestCase
from django.contrib.auth.models import User
from ordering.models import Passenger, Order
from django.core.urlresolvers import reverse
from django.utils import simplejson

from common.models import City, Country
import ordering
from ordering.pricing import estimate_cost, IsraelExtraCosts, CostType, TARIFF1_START, TARIFF2_START
from ordering.forms import OrderForm
from ordering.testing.meter_calculator import calculate_meter, calculate_tariff1, calculate_tariff2

import logging
import datetime


class OrderTest(TestCase):
#    fixtures = ['ordering/fixtures/initial_data.json']
    def setUp(self):
        test_user = User()
        test_user.username = 'testuser'
        test_user.set_password('testuser')
        test_user.first_name = 'testuser'
        test_user.email = 'testuser@exmaple.com'
        test_user.save()

        passenger = Passenger.objects.all()[0]
        passenger.user = test_user
        passenger.save()


    def login(self):
        login = self.client.login(username='testuser', password='testuser')
        self.failUnless(login, 'Could not log in')

    def test_show_order_form(self):

        self.login()

        response = self.client.get(reverse(ordering.passenger_controller.passenger_home))
        self.assertEqual(response.status_code, 200)
        self.failUnless(response.context, "context is None: %s" % response)

#        self.assertEquals(response.context["user"].username, "testuser")
#        self.assertEquals(response.context["user"].first_name, "testuser")

        self.assertTrue(isinstance(response.context["form"], OrderForm))

    def test_submit_order(self):

        self.login()

        post_data = {"from_raw": "some address",
                     "to_raw": "some other address"}

        response = self.client.post(reverse("ordering.passenger_controller.book_order"), post_data)
        self.assertEqual(response.status_code, 200)

        query = Order.objects.filter(from_raw = "some address")
        self.assertTrue(query.count() > 0, "order was not created")
        order = query[0]
        self.failUnless(order, "order was not created")

    
    def test_get_order_history(self):

        self.login()

        response = self.client.get(reverse('ordering.passenger_controller.get_orders_data'))
        self.assertEqual(response.status_code, 200)
        data = simplejson.loads(response.content)
        self.assertEqual(11, len(data))


class PricingTest(TestCase):

    fixtures = ['countries', 'cities', 'rules']

    def setUp(self):
        pass
    
    def test_estimate_cost(self):

        # init Israel test
        IL = Country.objects.filter(code="IL").get()
        city_a = City.objects.all().get(name="תל אביב יפו") #tel aviv
        city_b = City.objects.all().get(name="אור יהודה") # or yehuda
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

        expected_cost = calculate_tariff1(t, d) + extras_cost #phone order is automatically added to extras list
        cost, type = estimate_cost(t, d, IL.code, time=datetime.time(12, 00), extras=extras)
        logging.info("tariff 1 + extras' estimation: %d (expected %d)" % (cost, expected_cost))
        self.assertEqual((cost, type), (expected_cost, expected_type), "Cost calculation yielded wrong result")

        expected_cost = calculate_tariff2(t, d) + extras_cost #phone order is automatically added to extras list
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
            if rule.from_day == 1 and rule.from_hour == TARIFF1_START:
                expected_cost = rule.fixed_cost + phone_order_price
                cost, type = estimate_cost(t, d, IL.code, time=datetime.time(12, 00), cities=[city_a.id, city_b.id])
                logging.info("flat rate tariff1 test: %d (expected %d)" % (cost, expected_cost))
                self.assertEqual((cost, type), (expected_cost, expected_type), "Cost calculation yielded wrong result")

            if rule.from_day == 1 and rule.from_hour == TARIFF2_START:
                expected_cost = rule.fixed_cost + phone_order_price
                cost, type = estimate_cost(t, d, IL.code, time=datetime.time(21, 30), cities=[city_a.id, city_b.id])
                logging.info("flat rate tariff 2 test: %d (expected %d)" % (cost, expected_cost))
                self.assertEqual((cost, type), (expected_cost, expected_type), "Cost calculation yielded wrong result")

            if rule.from_day == 7:
                expected_cost = rule.fixed_cost + phone_order_price
                cost, type = estimate_cost(t, d, IL.code, cities=[city_a.id, city_b.id], day=7)
                logging.info("flat rate weekend test: %d (expected %d)" % (cost, expected_cost))
                self.assertEqual((cost, type), (expected_cost, expected_type), "Cost calculation yielded wrong result")