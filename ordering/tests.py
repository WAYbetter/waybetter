# -*- coding: utf-8 -*-
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse

from common.models import City, Country

import ordering
from ordering.models import Passenger, Order, WorkStation, Station, OrderAssignment, IGNORED, PENDING, ASSIGNED, ACCEPTED, Phone
from ordering.forms import OrderForm
from ordering.dispatcher import assign_order, choose_workstation
from ordering.order_manager import NO_MATCHING_WORKSTATIONS_FOUND, ORDER_HANDLED, OK, accept_order
import station_controller
import station_connection_manager
from ordering.station_connection_manager import set_heartbeat, is_workstation_available
from ordering.decorators import passenger_required, passenger_required_no_redirect, NOT_A_USER, NOT_A_PASSENGER, CURRENT_PASSENGER_KEY
from ordering.pricing import estimate_cost, IsraelExtraCosts, CostType, TARIFF1_START, TARIFF2_START, SABBATH_START

from testing import setup_testing_env
from testing.meter_calculator import calculate_tariff, tariff1_dict, tariff2_dict

import logging
import time
import datetime

PASSENGER = None
ORDER = None
ORDER_DATA = {}

def create_passenger():
    global PASSENGER

    test_user = User.objects.get(username='test_user')
    passenger = Passenger()
    passenger.user = test_user
    passenger.country = Country.objects.filter(code="IL").get()
    passenger.save()
    PASSENGER = passenger

def create_test_order():
    global ORDER
    global ORDER_DATA

    ORDER_DATA = {
        "from_city": u'1604',
        "from_country": u'12',
        "from_geohash": u'swnvcbg7d23u',
        "from_lat": u'32.073654',
        "from_lon": u'34.765465',
        "from_raw": u'Allenby 1, Tel Aviv Yafo',
        "from_street_address": u'Allenby',
        "geocoded_from_raw": u'Allenby 1, Tel Aviv Yafo',
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

def resuscitate_work_stations():
    for ws in WorkStation.objects.all():
        set_heartbeat(ws)


def set_accept_orders_true(ws_list):
    for ws in ws_list:
        ws.accept_orders = True
        ws.save()

def set_accept_orders_false(ws_list):
    for ws in ws_list:
        ws.accept_orders = False
        ws.save()

        
#
# testing starts here
#

class OrderingTest(TestCase):

    fixtures = ['countries.yaml', 'cities.yaml', 'ordering_test_data.yaml']

    def setUp(self):
        setup_testing_env.setup()

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

    fixtures = ['countries.yaml', 'cities.yaml', 'ordering_test_data.yaml']

    def setUp(self):
        setup_testing_env.setup()
        create_passenger()
        create_test_order()

    def test_book_order(self):
        # the call made by book_order_async
        response = self.client.post(reverse('ordering.order_manager.book_order'), data={"order_id": ORDER.id})

        # working stations are dead, assignment should fail
        self.assertTrue((response.content, response.status_code) == (NO_MATCHING_WORKSTATIONS_FOUND, 200), "Assignment should fail: workstations are dead")

        # resuscitate work stations and try again
        resuscitate_work_stations()
        response = self.client.post(reverse('ordering.order_manager.book_order'), data={"order_id": ORDER.id})
        self.assertTrue((response.content, response.status_code) == (ORDER_HANDLED, 200), "Assignment should succeed: workstations are live")

    def test_redispatch_ignored_orders(self):
        station = Station.objects.get(name='test_station_1')
        work_station = WorkStation.objects.filter(station=station)[0]

        # create a timed out assignment
        assignment = OrderAssignment(order=ORDER, station=station, work_station=work_station, status=ASSIGNED,
                                     create_date = datetime.datetime.now() - datetime.timedelta(seconds=OrderAssignment.ORDER_ASSIGNMENT_TIMEOUT+1))
        assignment.save()

        # check that it is dispatched and marked as ignored
        response = self.client.post(reverse('ordering.order_manager.redispatch_ignored_orders'), data={"order_assignment_id": assignment.id})
        self.assertTrue((response.content, response.status_code) == (OK, 200), "redispatch failed.")
        assignment = OrderAssignment.objects.get(id=assignment.id)
        self.assertTrue(assignment.status == IGNORED, "assignment should be marked as ignored.")

        # TODO_WB: make sure that a new task was added to the queue
        # apparently not supported, see http://code.google.com/appengine/docs/python/taskqueue/queues.html

    def test_accept_order(self):
        tel_aviv_station = City.objects.get(name="תל אביב יפו").stations.all()[0]
        phone1 = Phone(local_phone=u'1234567', station=tel_aviv_station)
        phone1.save()
        phone2 = Phone(local_phone=u'0000000', station=tel_aviv_station)
        phone2.save()

        accept_order(ORDER, pickup_time=5, station=tel_aviv_station)

        self.assertTrue((ORDER.status, ORDER.pickup_time, ORDER.station) == (ACCEPTED, 5, tel_aviv_station))

class StationConnectionTest(TestCase):
    """Unit test for the station connection manager."""

    fixtures = ['countries.yaml', 'cities.yaml', 'ordering_test_data.yaml']
    
    def setUp(self):
        setup_testing_env.setup()

    def test_ws_status_notification(self):
        service_url = reverse('ordering.station_controller.notify_ws_status')

        # nothing happened
        response = self.client.get(service_url)
        self.assertEqual(response.content, station_controller.OK)

        # work stations are born
        resuscitate_work_stations()
        response = self.client.get(service_url)
        self.assertEqual(response.content, station_controller.WS_BORN)

        # wait for IS_DEAD_DELTA time to go by without another heartbeat...
        time.sleep(station_connection_manager.IS_DEAD_DELTA + 1)
        response = self.client.get(service_url)
        self.assertEqual(response.content, station_controller.WS_DECEASED)

        # nothing happened
        response = self.client.get(service_url)
        self.assertEqual(response.content, station_controller.OK)


class DispatcherTest(TestCase):
    """Unit test for the dispatcher ordering logic."""

    fixtures = ['countries.yaml', 'cities.yaml', 'ordering_test_data.yaml']

    def setUp(self):
        setup_testing_env.setup()

    def test_assign_order(self):
        create_passenger()
        create_test_order()

        resuscitate_work_stations()
        assignment = assign_order(ORDER)

        self.assertTrue(assignment.station and assignment.work_station)
        self.assertTrue(isinstance(assignment, ordering.models.OrderAssignment))
        self.assertTrue((assignment.order, ORDER.status) == (ORDER, ASSIGNED))
        self.assertTrue(assignment.pickup_address_in_ws_lang == u'אלנבי 1, תל אביב יפו')

    def test_originating_station(self):
        global PASSENGER
        create_passenger()
        create_test_order()
        tel_aviv_station = City.objects.get(name="תל אביב יפו").stations.all()[0]

        # test default station is chosen over ws1 (ws2 has ignored this order)
        other_station_name = 'default station in tel aviv'
        other_ws_name = 'choose me'

        for user_name in [other_station_name, other_ws_name]:
            user = User(username=user_name)
            user.set_password(user_name)
            user.save()
        other_station = Station(name=other_station_name, user=User.objects.get(username=other_station_name), number_of_taxis=5,
                country=Country.objects.filter(code="IL").get(), city=City.objects.get(name="תל אביב יפו"), address='אחד העם 1 תל אביב', lat=32.063325, lon=34.768338)
        other_station.save()

        other_ws = WorkStation(user = User.objects.get(username=other_ws_name), station = other_station, was_installed = True, accept_orders = True)
        other_ws.save()

        ORDER.originating_station = tel_aviv_station
        ORDER.save()

          # the call made by book_order_async
        response = self.client.post(reverse('ordering.order_manager.book_order'), data={"order_id": ORDER.id})
        PASSENGER = Passenger.objects.get(id=PASSENGER.id) # refresh passenger
        self.assertTrue(PASSENGER.originating_station == tel_aviv_station, "PASSENGER.originating_station should be tel_aviv_station and not %s" % PASSENGER.originating_station)

        # resuscitate work stations and try again
        resuscitate_work_stations()
        self.assertTrue(choose_workstation(ORDER).station == tel_aviv_station, "Other Tel Aviv station is expected")
        tel_aviv_station.last_assignment_date = datetime.datetime.now()
        tel_aviv_station.save()

        self.assertTrue(choose_workstation(ORDER).station == tel_aviv_station, "Other Tel Aviv station is expected")

    def test_choose_workstation(self):
        create_passenger()
        create_test_order()

        tel_aviv_station = City.objects.get(name="תל אביב יפו").stations.all()[0]
        tel_aviv_ws1 = WorkStation.objects.filter(station=tel_aviv_station)[0]
        tel_aviv_ws2 = WorkStation.objects.filter(station=tel_aviv_station)[1]

        jerusalem_station = City.objects.get(name="ירושלים").stations.all()[0]
        jerusalem_ws = WorkStation.objects.filter(station=jerusalem_station)[0]

        # work stations are dead
        ws = choose_workstation(ORDER)
        self.assertTrue(ws is None, "work station are dead, none is expected, got %s" % ws)

        # live work station but it's in Jerusalem (order is from tel aviv)
        set_heartbeat(jerusalem_ws)
        ws = choose_workstation(ORDER)
        self.assertTrue(ws is None, "tel aviv work station are dead, none is expected, got %s" % ws)

        # live but don't accept orders
        set_accept_orders_false([tel_aviv_ws1, tel_aviv_ws2])
        set_heartbeat(tel_aviv_ws1)
        self.assertTrue(choose_workstation(ORDER) is None, "tel aviv work station don't accept orders, none is expected.")

        # tel_aviv_ws2 is live and accepts orders
        set_accept_orders_true([tel_aviv_ws2])
        resuscitate_work_stations()
        self.assertTrue(choose_workstation(ORDER) == tel_aviv_ws2, "tel aviv work station 2 is expected.")

        # mark this order as previously ignored by ws2, should return ws1
        assignment = OrderAssignment(order=ORDER, station=tel_aviv_station, work_station=tel_aviv_ws2, status=IGNORED)
        assignment.save()

        set_accept_orders_true([tel_aviv_ws1, tel_aviv_ws2])
        resuscitate_work_stations()

        self.assertTrue(choose_workstation(ORDER) == tel_aviv_ws1, "tel aviv work station 1 is expected.")

        # test default station is chosen over ws1 (ws2 has ignored this order)
        default_station_name = 'default station in tel aviv'
        default_ws_name = 'choose me'

        for user_name in [default_station_name, default_ws_name]:
            user = User(username=user_name)
            user.set_password(user_name)
            user.save()

        default_station = Station(name=default_station_name, user=User.objects.get(username=default_station_name), number_of_taxis=5,
                country=Country.objects.filter(code="IL").get(), city=City.objects.get(name="תל אביב יפו"), address='אחד העם 1 תל אביב', lat=32.063325, lon=34.768338)
        default_station.save()

        default_ws = WorkStation(user = User.objects.get(username=default_ws_name), station = default_station, was_installed = True, accept_orders = True)
        default_ws.save()

        PASSENGER.default_station = default_station
        PASSENGER.save()

        resuscitate_work_stations()
        self.assertTrue(choose_workstation(ORDER) == default_ws, "default station is expected.")

        # check that the dispatcher is "fair": chooses first the last station that was given an order
        PASSENGER.default_station = None
        PASSENGER.save()

        default_station.last_assignment_date = datetime.datetime.now()
        default_station.save()

        self.assertTrue(choose_workstation(ORDER).station == tel_aviv_station, "Other Tel Aviv station is expected")

        tel_aviv_station.last_assignment_date = datetime.datetime.now()
        tel_aviv_station.save()

        self.assertTrue(choose_workstation(ORDER).station == default_station, "Other Tel Aviv station is expected")



class PricingTest(TestCase):
    """
    Unit test for pricing algorithm.
    """
    fixtures = ['countries.yaml', 'cities.yaml', 'pricing_test_data']

    def setUp(self):
        # init Israel test
        self.IL = Country.objects.filter(code="IL").get()
        self.phone_order_price = self.IL.extra_charge_rules.get(rule_name=IsraelExtraCosts.PHONE_ORDER).cost
        self.t, self.d = 768, 4110
        logging.info("Testing meter cost estimation, with estimated duration: %d & estimated distance: %d" % (self.t, self.d))

    def test_meter_cost(self):
        IL = self.IL
        t, d = self.t, self.d
        
        expected_type = CostType.METER
        extras = [IsraelExtraCosts.NATBAG_AIRPORT, IsraelExtraCosts.KVISH_6]
        extras_cost = sum([IL.extra_charge_rules.get(rule_name=extra).cost for extra in extras])

        # tariff 1 test
        expected_cost = calculate_tariff(t, d, tariff1_dict) + self.phone_order_price

        cost, type = estimate_cost(t, d, IL.code, day=1,time=datetime.time(05, 30, 00))
        self.assertEqual((cost, type), (expected_cost, expected_type), "tariff 1 estimation failed: %d (expected %d)" % (cost, expected_cost))
        cost, type = estimate_cost(t, d, IL.code, day=1, time=datetime.time(20, 59, 59))
        self.assertEqual((cost, type), (expected_cost, expected_type), "tariff 1 estimation failed: %d (expected %d)" % (cost, expected_cost))
        cost, type = estimate_cost(t, d, IL.code, day=6, time=datetime.time(16, 59, 59))
        self.assertEqual((cost, type), (expected_cost, expected_type), "Friday estimation failed: %d (expected %d)" % (cost, expected_cost))

        expected_cost += extras_cost
        cost, type = estimate_cost(t, d, IL.code, time=datetime.time(12, 00), extras=extras)
        self.assertEqual((cost, type), (expected_cost, expected_type), "tariff 1 + extras' estimation failed: %d (expected %d)" % (cost, expected_cost))

        # tariff2 test
        expected_cost = calculate_tariff(t, d, tariff2_dict) + self.phone_order_price

        cost, type = estimate_cost(t, d, IL.code, day=1, time=datetime.time(21, 00, 00))
        self.assertEqual((cost, type), (expected_cost, expected_type), "tariff 2 estimation failed: %d (expected %d)" % (cost, expected_cost))
        cost, type = estimate_cost(t, d, IL.code, day=1, time=datetime.time(05, 29, 59))
        self.assertEqual((cost, type), (expected_cost, expected_type), "tariff 2 estimation failed: %d (expected %d)" % (cost, expected_cost))
        cost, type = estimate_cost(t, d, IL.code, day=6, time=datetime.time(17, 00, 00))
        self.assertEqual((cost, type), (expected_cost, expected_type), "Friday estimation failed: %d (expected %d)" % (cost, expected_cost))
        cost, type = estimate_cost(t, d, IL.code, day=7, time=datetime.time(23, 59, 59))
        self.assertEqual((cost, type), (expected_cost, expected_type), "Saturday estimation failed: %d (expected %d)" % (cost, expected_cost))

        expected_cost += extras_cost
        cost, type = estimate_cost(t, d, IL.code, time=datetime.time(22, 00), extras=extras)
        self.assertEqual((cost, type), (expected_cost, expected_type), "tariff 2 + extras' estimation failed: %d (expected %d)" % (cost, expected_cost))

    def test_flat_rate_cost(self):
        IL = self.IL
        t, d = self.t, self.d
        city_a = City.objects.get(name="תל אביב יפו")
        city_b = City.objects.get(name="אור יהודה")

        expected_type = CostType.FLAT
        logging.info("Testing flat rate prices, with cities: %s , %s" % (city_a.name, city_b.name))

        flat_rate_rules = IL.flat_rate_rules.filter(city1=city_a,city2=city_b)
        if not flat_rate_rules:
            flat_rate_rules = IL.flat_rate_rules.filter(city1=city_b,city2=city_a)

        self.assertTrue(flat_rate_rules, "No flat rate rule found between cities %s, %s" % (city_a.name,city_b.name))
        expected_cost_tariff1 = min([r.fixed_cost for r in flat_rate_rules]) + self.phone_order_price
        expected_cost_tariff2 = max([r.fixed_cost for r in flat_rate_rules]) + self.phone_order_price

        # tariff 1 test
        cost, type = estimate_cost(t, d, IL.code, day=1, time=datetime.time(12, 00), cities=[city_a.id, city_b.id])
        self.assertEqual((cost, type), (expected_cost_tariff1, expected_type), "flat rate tariff1 test failed: %d (expected %d)" % (cost, expected_cost_tariff1))

        cost, type = estimate_cost(t, d, IL.code, day=6, time=datetime.time(16, 59), cities=[city_a.id, city_b.id])
        self.assertEqual((cost, type), (expected_cost_tariff1, expected_type), "flat rate tariff1 test failed: %d (expected %d)" % (cost, expected_cost_tariff1))

        # tariff 2 test
        cost, type = estimate_cost(t, d, IL.code, day=1, time=datetime.time(21, 01), cities=[city_a.id, city_b.id])
        self.assertEqual((cost, type), (expected_cost_tariff2, expected_type), "flat rate tariff2 test failed: %d (expected %d)" % (cost, expected_cost_tariff2))

        cost, type = estimate_cost(t, d, IL.code, day=6, time=datetime.time(17, 01), cities=[city_a.id, city_b.id])
        self.assertEqual((cost, type), (expected_cost_tariff2, expected_type), "flat rate tariff2 test failed: %d (expected %d)" % (cost, expected_cost_tariff2))

        cost, type = estimate_cost(t, d, IL.code, day=7, time=datetime.time(12, 01), cities=[city_a.id, city_b.id])
        self.assertEqual((cost, type), (expected_cost_tariff2, expected_type), "flat rate tariff2 test failed: %d (expected %d)" % (cost, expected_cost_tariff2))
