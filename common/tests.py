# This Python file uses the following encoding: utf-8
"""
This file demonstrates two different styles of tests (one doctest and one
unittest). These will both pass when you run "manage.py test".

Replace these with more appropriate tests for your application.
"""

from django.test import TestCase
import common.urllib_adaptor as urllib2
import logging
from common.route import calculate_time_and_distance


class GeocodeTest(TestCase):
    def test_geocoding(self):
       pass


class Urllib2AdaptorTest(TestCase):
    def test_fetch_url(self):
        content = urllib2.urlopen("http://www.google.com")
        self.assertTrue("google" in str(content))

    def test_content_read(self):
        response = urllib2.urlopen("http://www.google.com")
        content = response.read()
        self.assertTrue("google" in content)

    def test_request_headers(self):
        mobile_str = "mobile.twitter.com"
        url = "http://www.twitter.com"
        request = urllib2.Request(url,
                                  headers={"USER_AGENT": "Mozilla/5.0 (iPhone; U; CPU iPhone OS 3_0 like Mac OS X; en-us) AppleWebKit/420.1 (KHTML, like Gecko) Version/3.0 Mobile/1A542a Safari/419.3"})

        content = urllib2.urlopen(request)
        self.assertTrue(mobile_str in str(content))

        request = urllib2.Request(url)
        content = urllib2.urlopen(request)
        self.assertTrue(mobile_str not in str(content))


class RouteTest(TestCase):
    # need margins to take into account traffic noise.
    TIME_ERROR_MARGIN = 120
    DISTANCE_ERROR_MARGIN = 2000

    def test_calculate_time_and_distance(self):
        logging.info("Testing route from p0=Yishayahu 60 to p1=Rotschild 19")
        p0_x, p0_y = '34.78099', '32.09307'
        p1_x, p1_y = '34.77127', '32.06355'
        (t, d) = calculate_time_and_distance(p0_x, p0_y, p1_x, p1_y)
        (expected_t, expected_d) = (768, 4110)
        logging.info("Time received: %d (expected %d)" % (t, expected_t))
        logging.info("Distance received: %d (expected %d)" % (d, expected_d))
        self.assertTrue(abs(t-expected_t) < self.TIME_ERROR_MARGIN)
        self.assertTrue(abs(d-expected_d) < self.DISTANCE_ERROR_MARGIN)
