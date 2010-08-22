# This Python file uses the following encoding: utf-8
"""
This file demonstrates two different styles of tests (one doctest and one
unittest). These will both pass when you run "manage.py test".

Replace these with more appropriate tests for your application.
"""

from django.test import TestCase
from common.geocode import waze_geocode
from common.util import is_empty
import common.urllib_adaptor as urllib2


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


__test__ = {
    'doctest': """
    Test is_empty

>>> is_empty(" a ")
False
>>> is_empty(None)
True
>>> is_empty("             ")
True
>>> is_empty("")
True
"""
}