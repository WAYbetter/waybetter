from django.test import TestCase
from django.contrib.auth.models import User
from ordering.models import Passenger, Order
from django.core.urlresolvers import reverse
from django.utils import simplejson
import ordering
from ordering.forms import OrderForm
import logging

from pricing2 import estimate_cost
from common.models import City
from meterCalc import calculate_meter
import datetime

from django.shortcuts import render_to_response
from django.template import RequestContext
from common.util import custom_render_to_response


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
        t, d = 768, 4110
        city_a = City.objects.all().filter(id=1604).get()
        city_b = City.objects.all().filter(id=1744).get()

        # tariff 1 test
        logging.info("Testing tariff 1 estimation, with estimated duration: %d & estimated distance: %d" % (t, d))
        cost = estimate_cost(t, d, country_code="IL", time=datetime.time(12,00))
        expected_cost = 32.7
        logging.info("Cost calculation result: %d (expected %d)" % (cost, expected_cost))
        self.assertEqual(expected_cost, cost, "Cost calculation yielded wrong result")

        # night test
        logging.info("Testing night estimation, with estimated duration: %d & estimated distance: %d" % (t, d))
        cost = estimate_cost(t, d, country_code="IL", time=datetime.time(21,30))
        expected_cost = 37.5
        logging.info("Cost calculation result: %d (expected %d)" % (cost, expected_cost))
        self.assertEqual(expected_cost, cost, "Cost calculation yielded wrong result")

        # weekend test
        logging.info("Testing weekend estimation, with estimated duration: %d & estimated distance: %d" % (t, d))
        cost = estimate_cost(t, d, country_code="IL",day=7)
        expected_cost = 37.5
        logging.info("Cost calculation result: %d (expected %d)" % (cost, expected_cost))
        self.assertEqual(expected_cost, cost, "Cost calculation yielded wrong result")

        # flat rate
        logging.info("Testing flat rate estimation, from %s to %s" % (city_a.name, city_b.name))
        cost_tariff1 = estimate_cost(t, d, country_code="IL",time=datetime.time(12,00),cities=[city_a,city_b])
        cost_tariff2 = estimate_cost(t, d, country_code="IL",time=datetime.time(21,30),cities=[city_a,city_b])
        cost_weekend = estimate_cost(t, d, country_code="IL",cities=[city_a,city_b], day=7)
        
        expected_cost = 66
        logging.info("Cost calculation result: %d (expected %d)" % (cost, expected_cost))
        self.assertEqual(expected_cost, cost, "Cost calculation yielded wrong result")

        # test with special place

        # test with special city