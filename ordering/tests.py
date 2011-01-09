# -*- coding: utf-8 -*-
from django.test import TestCase
from django.contrib.auth.models import User
from ordering.models import Passenger, Order
from django.core.urlresolvers import reverse
from django.utils import simplejson

from common.models import City
import ordering
from ordering.pricing import estimate_cost, NATBAG_AIRPORT
from ordering.forms import OrderForm
from ordering.testing.meter_calculator import calculate_meter

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


class PricingCalculationTest(TestCase):

    def test_estimate_cost(self):

        city_a = City.objects.all().get(name="תל אביב יפו") #tel aviv
        city_b = City.objects.all().get(name="אור יהודה") # or yehuda

        t, d = 768, 4110

        # tariff 1 test
        logging.info("Testing tariff 1 estimation, with estimated duration: %d & estimated distance: %d" % (t, d))
        cost = estimate_cost(t, d, country_code="IL", time=datetime.time(12,00))
        expected_cost = calculate_meter(t,d,datetime.time(05,30),1)
        logging.info("Cost calculation result: %d (expected %d)" % (cost, expected_cost))
        self.assertEqual(expected_cost, cost, "Cost calculation yielded wrong result")

        # tariff2 test
        logging.info("Testing tariff2 estimation, with estimated duration: %d & estimated distance: %d" % (t, d))
        cost = estimate_cost(t, d, country_code="IL", time=datetime.time(21,30))
        expected_cost = calculate_meter(t,d,datetime.time(21,01),1)
        logging.info("Cost calculation result: %d (expected %d)" % (cost, expected_cost))
        self.assertEqual(expected_cost, cost, "Cost calculation yielded wrong result")

        # weekend test
        logging.info("Testing weekend estimation, with estimated duration: %d & estimated distance: %d" % (t, d))
        cost = estimate_cost(t, d, country_code="IL",day=7)
        expected_cost = calculate_meter(t,d,datetime.time(12,00),7)
        logging.info("Cost calculation result: %d (expected %d)" % (cost, expected_cost))
        self.assertEqual(expected_cost, cost, "Cost calculation yielded wrong result")

        # flat rate
        logging.info("Testing flat rate tariff1 estimation, from %s to %s" % (city_a.name, city_b.name))
        cost = estimate_cost(t, d, country_code="IL",time=datetime.time(12,00),cities=[city_a.id, city_b.id])
        expected_cost = 66+4.5
        logging.info("Cost calculation result: %d (expected %d)" % (cost, expected_cost))
        self.assertEqual(expected_cost, cost, "Cost calculation yielded wrong result")

        logging.info("Testing flat rate tariff2 estimation, from %s to %s" % (city_a.name, city_b.name))
        cost = estimate_cost(t, d, country_code="IL",time=datetime.time(21,30),cities=[city_a.id, city_b.id])
        expected_cost = 69+4.5
        logging.info("Cost calculation result: %d (expected %d)" % (cost, expected_cost))
        self.assertEqual(expected_cost, cost, "Cost calculation yielded wrong result")

        logging.info("Testing flat rate weekend estimation, from %s to %s" % (city_a.name, city_b.name))
        cost = estimate_cost(t, d, country_code="IL",cities=[city_a.id, city_b.id], day=7)
        expected_cost = 69+4.5
        logging.info("Cost calculation result: %d (expected %d)" % (cost, expected_cost))
        self.assertEqual(expected_cost, cost, "Cost calculation yielded wrong result")

        # test with extra charge
        logging.info("Testing tariff 1 + extras estimation, with estimated duration: %d & estimated distance: %d" % (t, d))
        cost = estimate_cost(t, d, country_code="IL", time=datetime.time(12,00), extras=[NATBAG_AIRPORT])
        expected_cost = calculate_meter(t,d,datetime.time(05,30),1)+5
        logging.info("Cost calculation result: %d (expected %d)" % (cost, expected_cost))
        self.assertEqual(expected_cost, cost, "Cost calculation yielded wrong result")

        # test with special city