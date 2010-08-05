# This Python file uses the following encoding: utf-8
"""
This file demonstrates two different styles of tests (one doctest and one
unittest). These will both pass when you run "manage.py test".

Replace these with more appropriate tests for your application.
"""

from django.test import TestCase
from common.geocode import waze_geocode
from common.util import is_empty

class GeocodeTest(TestCase):
    def test_geocoding(self):
       pass


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