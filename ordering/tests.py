"""
This file demonstrates two different styles of tests (one doctest and one
unittest). These will both pass when you run "manage.py test".

Replace these with more appropriate tests for your application.
"""

from django.test import TestCase
from django.contrib.auth.models import User
from ordering.models import Passenger, Order
from ordering.forms import OrderForm

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
        
        response = self.client.get("/passenger/")
        self.assertEqual(response.status_code, 200)
        self.failUnless(response.context, "context is None: %s" % response)

        self.assertEquals(response.context["user"].username, "testuser")
        self.assertEquals(response.context["user"].first_name, "testuser")

        self.assertTrue(isinstance(response.context["form"], OrderForm))

    def test_submit_order(self):

        self.login()

        post_data = {"from_raw": "some address",
                     "to_raw": "some other address"}

        response = self.client.post("/passenger/", post_data)
        self.assertEqual(response.status_code, 200)

        order = Order.objects.filter(from_raw = "some address")[0]
        self.failUnless(order, "order was not created")






