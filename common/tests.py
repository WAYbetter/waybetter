# This Python file uses the following encoding: utf-8
from django.core.urlresolvers import reverse
from django.test import TestCase

import common.urllib_adaptor as urllib2
from common.geo_calculations import distance_between_points
from common.geocode import geocode, geohash_encode, geohash_decode
from common.sms_notification import send_sms
from common.route import calculate_time_and_distance

import logging

class GeocodeTest(TestCase):
    """
    Geocoding unitTest: geo coding, geo distance and geo hashing tests.
    """

    def test_geo_coding(self):
        """
        Check that geocoding returns at least one location with correct geocode,
        i.e., country, city, street, house number, lon. and lat. are matching those of the query.
        """
        test_data = (
            {"address"      : u"דיזנגוף 99 תל אביב",
             "country"      : u"IL",
             "city"         : u"תל אביב יפו",
             "street"       : u"דיזנגוף",
             "house_number" : u"99",
             "lon"          : '34.77388',
             "lat"          : '32.07933',
        },
            {"address"      : u"מרג 1 תל אביב יפו",
             "country"      : u"IL",
             "city"         : u"תל אביב יפו",
             "street"       : u"מרגולין",
             "house_number" : u"1",
             "lon"          : '34.787368',
             "lat"          : '32.05856',
        },
            {"address"      : u"בן יהודה 35 ירושלים",
             "country"      : u"IL",
             "city"         : u"ירושלים",
             "street"       : u"בן יהודה",
             "house_number" : u"35",
             "lon"          : '35.214161',
             "lat"          : '31.780725',
            },
        )
        
        logging.info("\nTesting geo coding")
        for test_case in test_data:
            test_case_success = False

            address = test_case["address"]
            logging.info("Testing geo coding for %s" % address)
            geo_code = geocode(address)
            self.assertTrue(geo_code, msg="no geo code received for %s" % address)

            # geo_code may contain more than one location. Check that at least one is correct.
            for location in geo_code:
                location_success = True
                logging.info("Processing location %s" % location["description"])

                # textual properties, compare lowercase
                for property in ["country", "city", "street", "house_number"]:
                    result = "OK"
                    if not test_case[property].lower() == location[property].lower():
                        result = "failed"
                        location_success = False
                    #uncomment for debug since all Django tests run with DEBUG=False
                    #logging.info("comparing %s: %s" % (property, result))

                # numerical properties, allowed to differ a bit.
                precision = 0.001
                result = "OK"
                for property in ["lon", "lat"]:
                    if not abs(float(test_case[property]) - float(location[property])) < precision:
                        result = "failed"
                        location_success = False
                    #logging.info("comparing %s with precision %f: %s" % (property, precision, result))

                if location_success:
                    logging.info("Found correct location at %s" % location["description"])
                    test_case_success = True
                    break

            self.assertTrue(test_case_success, msg="correct geo code was not found for %s" % address)


    def test_geo_distance(self):
        """
        Test geo distance calculation. Taken from Jan Matuschek's article.
        """
        logging.info("\nTesting geo distance liberty to eiffel")
        # distance is about 5837 km, check 3 decimal places
        d = distance_between_points(40.6892, -74.0444, 48.8583, 2.2945)
        expected_d = 5837.413
        self.assertAlmostEqual(d, expected_d, places=3, msg="geo distance error %f (expected %f)" % (d, expected_d))

    def test_geo_hash(self):
        """
        Simple geo hasing test.
        """
        logging.info("\nTesting geohash encode/decode.")
        points = ({"lon"       :"31.776933",
                   "lat"       :"35.234376",
                   "hash_code" :"sv9hcbbfh3wu"},
                  {"lon"       :"21.424172",
                   "lat"       :"39.826112",
                   "hash_code" :"sgu3fk0kzejk"},
                  )
        for p in points:
            self.assertEqual(geohash_encode(float(p["lon"]),float(p["lat"])), p["hash_code"], msg="encode error")
            self.assertEqual(geohash_decode(p["hash_code"]), (p["lon"],p["lat"]), msg="decode error")


class RouteTest(TestCase):
    """
    Unit test for route estimation (time and distance).
    """

    def setUp(self):
        # error margins to take into account traffic noise.
        self.ERR_RATIO = 0.4

        self.test_data = (
            {"p0"         : "Yishayahu 60 Tel Aviv",
             "p1"         : "Rotschild 19 Tel Aviv",
             "p0_x"       : '34.78099',
             "p0_y"       : '32.09307',
             "p1_x"       : '34.77127',
             "p1_y"       : '32.06355',
             "expected_t" : '768',
             "expected_d" : '4110'
        },
            {"p0"         : "Tarsish 17 Or Yehuda",
             "p1"         : "Margolin 15 Tel Aviv",
             "p0_x"       : '34.859405',
             "p0_y"       : '32.028877',
             "p1_x"       : '34.790611',
             "p1_y"       : '32.05856',
             "expected_t" : '900',
             "expected_d" : '12000'
            }
        )

    def test_calculate_time_and_distance(self):
        for test_case in self.test_data:
            logging.info("Testing route from %s (p0) to %s (p1)" % (test_case["p0"], test_case["p1"]))
            estimation = calculate_time_and_distance(test_case["p0_x"], test_case["p0_y"], test_case["p1_x"], test_case["p1_y"])

            t, d = float(estimation["estimated_duration"]), float(estimation["estimated_distance"])
            expected_t, expected_d = float(test_case["expected_t"]), float(test_case["expected_d"])

            logging.info("Time received: %d (expected %d)" % (t, expected_t))
            self.assertTrue(1 - self.ERR_RATIO < t/expected_t < 1 + self.ERR_RATIO)

            logging.info("Distance received: %d (expected %d)" % (d, expected_d))
            self.assertTrue(1 - self.ERR_RATIO < d/expected_d < 1 + self.ERR_RATIO)


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


class BasicFuncTest(TestCase):
    """
    Test basic functionality provided by common app.
    """

    fixtures = ['countries.yaml']
    
    def test_send_sms(self):
        logging.info("\nTesting sms sending")
        self.assertTrue(send_sms('+972-3-1234567', 'sms test'), msg="sms send failed")

    def test_is_username_available(self):
        logging.info("\nTesting username available")
        from django.contrib.auth.models import User
        test_user = User()
        test_user.username = "test_user1"
        test_user.save()

        response = self.client.get(reverse('common.services.is_username_available'), {"username": "test_user1"})
        self.assertTrue(response.content == "false", msg="expected username unavailable")

        response = self.client.get(reverse('common.services.is_username_available'), {"username": "test_user2"})
        self.assertTrue(response.content == "true", msg="expected username unavailable")

