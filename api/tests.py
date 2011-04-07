# -*- coding: utf-8 -*-

from django.core.urlresolvers import reverse
from django.template.context import Context
from django.template.loader import get_template
from django.test import TestCase

from testing import setup_testing_env

GOOD_PASSENGER_PHONE    = '000000000'
BAD_PASSENGER_PHONE     = '123'
GOOD_API_KEY            = "abcde"
BAD_API_KEY             = "foo"
GOOD_STREET_NAME        = u"ישעיהו"
BAD_STREET_NAME         = "xxxxxxxxxx"

class APITest(TestCase):
    fixtures = ['countries.yaml', 'cities.yaml', 'ordering_test_data.yaml', 'passenger.yaml', 'apiuser.yaml']

    def setUp(self):
        setup_testing_env.setup()
        
    def test_order_ride(self):
        url = reverse('order_ride_api')
        t = get_template("order_ride.xml")

        c = Context({
            'passenger_phone'   : GOOD_PASSENGER_PHONE,
            'api_user_key'      : GOOD_API_KEY,
            'street_name'       : GOOD_STREET_NAME
            })
        
        res = self.client.post(url, data=(t.render(c)), content_type="text/xml")
        self.assertEqual(res.status_code, 201) # Created

        c = Context({
            'passenger_phone'   : BAD_PASSENGER_PHONE,
            'api_user_key'      : GOOD_API_KEY,
            'street_name'       : GOOD_STREET_NAME
        })

        res = self.client.post(url, data=(t.render(c)), content_type="text/xml")
        self.assertEqual(res.status_code, 404) # Not Found

        c = Context({
            'passenger_phone'   : GOOD_PASSENGER_PHONE,
            'api_user_key'      : BAD_API_KEY,
            'street_name'       : GOOD_STREET_NAME
        })

        res = self.client.post(url, data=(t.render(c)), content_type="text/xml")
        self.assertEqual(res.status_code, 401) # Forbidden

        c = Context({
            'passenger_phone'   : GOOD_PASSENGER_PHONE,
            'api_user_key'      : GOOD_API_KEY,
            'street_name'       : BAD_STREET_NAME
            })

        res = self.client.post(url, data=(t.render(c)), content_type="text/xml")
        self.assertContains(res, "Bad Request 1004", status_code=400) # Invalid Address

    def test_get_ride_estimate(self):
        url = reverse('get_ride_estimation_api')
        t = get_template("ride_estimate.xml")

        c = Context({
            'api_user_key'      : GOOD_API_KEY,
            'street_name'       : GOOD_STREET_NAME
        })

        res = self.client.post(url, data=(t.render(c)), content_type="text/xml")
        self.assertContains(res, "estimated_duration", count=2)
        self.assertContains(res, "estimated_distance", count=2)

        c = Context({
            'api_user_key'      : BAD_API_KEY,
            'street_name'       : GOOD_STREET_NAME
        })

        res = self.client.post(url, data=(t.render(c)), content_type="text/xml")
        self.assertEqual(res.status_code, 401) # Forbidden

        c = Context({
            'api_user_key'      : GOOD_API_KEY,
            'street_name'       : BAD_STREET_NAME
        })

        res = self.client.post(url, data=(t.render(c)), content_type="text/xml")
        self.assertContains(res, "Bad Request 1004", status_code=400) # Invalid Address


#TODO_WB: Add tests for form error codes
#TODO_WB: Test that order created via api has api_user attached to it.