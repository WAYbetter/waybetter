# -*- coding: utf-8 -*-
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from google.appengine.api import memcache

from common.models import City, Country

from ordering.models import Passenger, WorkStation, Station, Order, OrderAssignment, IGNORED, REJECTED, ASSIGNED, ACCEPTED, Phone, ORDER_ASSIGNMENT_TIMEOUT, ORDER_TEASER_TIMEOUT, NOT_TAKEN, ORDER_HANDLE_TIMEOUT, PENDING
from ordering.forms import OrderForm
from ordering.dispatcher import assign_order, choose_workstation, compute_ws_list
from ordering import order_manager
from ordering.order_manager import NO_MATCHING_WORKSTATIONS_FOUND, ORDER_HANDLED, ORDER_TIMEOUT
from ordering import station_controller
from ordering.station_connection_manager import get_heartbeat_key, set_heartbeat
from ordering.station_controller import ALERT_DELTA
from ordering.decorators import NOT_A_PASSENGER
from ordering.pricing import estimate_cost, IsraelExtraCosts, CostType, setup_israel_meter_and_extra_charge_rules, tariff1_dict, tariff2_dict
from ordering.rules_controller import add_flat_rate_rule

from testing import setup_testing_env
from testing.meter_calculator import calculate_tariff

import logging
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

    country_id = Country.objects.get(code='IL').id
    city_id = City.objects.get(name=u'תל אביב יפו').id
    ORDER_DATA = {
        "from_city": city_id,
        "from_country": country_id,
        "from_geohash": u'swnvcbg7d23u',
        "from_lat": u'32.073654',
        "from_lon": u'34.765465',
        "from_raw": u'Allenby 1, Tel Aviv Yafo',
        "from_street_address": u'Allenby',
        "from_house_number": u'1',
        "geocoded_from_raw": u'Allenby 1, Tel Aviv Yafo',
        "to_city": city_id,
        "to_country": country_id,
        "to_geohash": u'swnvcbdruxgz',
        "to_lat": u'32.07238',
        "to_lon": u'34.764862',
        "to_raw": u'גאולה 1, תל אביב יפו',
        "to_street_address": u'גאולה',
        "to_house_number": u'1',
        "geocoded_to_raw": u'גאולה 1, תל אביב יפו',
        # junk field
        "foo": "bar",
    }

    form = OrderForm(data=ORDER_DATA, passenger=PASSENGER)
    order = form.save()
    order.passenger = PASSENGER
    order.save()
    ORDER = order

# TODO_WB : fixtures to create another station in tel aviv
def create_another_TLV_station():
    # create another station in TLV
    tel_aviv = City.objects.get(name=u'תל אביב יפו')
    other_station_name = 'tel aviv %d' % (Station.objects.filter(city=tel_aviv).count()+1)
    other_ws_name = "%s_%s" % (other_station_name, "ws1")

    for user_name in [other_station_name, other_ws_name]:
        user = User(username=user_name)
        user.set_password(user_name)
        user.save()
    other_station = Station(name=other_station_name, user=User.objects.get(username=other_station_name), number_of_taxis=5,
                            country=Country.objects.filter(code="IL").get(), city=City.objects.get(name="תל אביב יפו"), address='גאולה 12', lat=32.071838, lon=34.766906)

    other_station.save()

    other_ws = WorkStation(user = User.objects.get(username=other_ws_name), station = other_station, was_installed = True, accept_orders = True)
    other_ws.save()

    return other_station

def refresh_order():
    global ORDER
    ORDER = Order.objects.get(id=ORDER.id)
    memcache.set('ws_list_for_order_%s' % ORDER.id, []) # make ORDER look fresh

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

        # login with no passenger, forbidden
        self.client.login(username='test_user_no_passenger', password='test_user_no_passenger')
        response = self.client.post(reverse('ordering.passenger_controller.book_order'))
        self.assertTrue((response.content, response.status_code) == (NOT_A_PASSENGER, 403))
        self.client.logout()

        # login with passenger, should be OK
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
        self.station = Station.objects.get(name='test_station_1')
        self.work_station = WorkStation.objects.filter(station=self.station)[0]
        self.assignment = OrderAssignment(order=ORDER, station=self.station, work_station=self.work_station)
        self.assignment.save()
        # TODO_WB: remove when we have new fixtures
        phone1 = Phone(local_phone=u'1234567', station=self.station)
        phone1.save()
        phone2 = Phone(local_phone=u'0000000', station=self.station)
        phone2.save()

    def test_book_order(self):
        response = self.client.post(reverse('ordering.order_manager.book_order'), data={"order_id": ORDER.id})

        # working stations are dead, assignment should fail
        self.assertTrue((response.content, response.status_code) == (NO_MATCHING_WORKSTATIONS_FOUND, 200), "Assignment should fail: workstations are dead")

        # resuscitate work stations and try again
        resuscitate_work_stations()
        response = self.client.post(reverse('ordering.order_manager.book_order'), data={"order_id": ORDER.id})
        self.assertTrue((response.content, response.status_code) == (ORDER_HANDLED, 200), "Assignment should succeed: workstations are live")

        # timed out order
        ORDER.create_date = datetime.datetime.now() - datetime.timedelta(seconds=ORDER_HANDLE_TIMEOUT+1)
        ORDER.save()
        response = self.client.post(reverse('ordering.order_manager.book_order'), data={"order_id": ORDER.id})
        self.assertTrue((response.content, response.status_code) == (ORDER_TIMEOUT, 200), "Assignment should fail: order time out")

    def test_redispatch_orders(self):
        assignment = self.assignment

        # NOT_TAKEN assignment
        assignment.create_date = datetime.datetime.now() - datetime.timedelta(seconds=ORDER_TEASER_TIMEOUT+1)
        assignment.save()
        self.client.post(reverse('ordering.order_manager.redispatch_pending_orders'), data={"order_assignment_id": assignment.id})
        assignment = OrderAssignment.objects.get(id=assignment.id) # refresh
        self.assertTrue(assignment.status == NOT_TAKEN, "assignment should be marked as not taken.")

        # IGNORED assignment
        assignment.status = ASSIGNED
        assignment.create_date = datetime.datetime.now() - datetime.timedelta(seconds=ORDER_ASSIGNMENT_TIMEOUT+1)
        assignment.save()
        self.client.post(reverse('ordering.order_manager.redispatch_ignored_orders'), data={"order_assignment_id": assignment.id})
        assignment = OrderAssignment.objects.get(id=assignment.id) # refresh
        self.assertTrue(assignment.status == IGNORED, "assignment should be marked as ignored.")

    def test_show_and_accept_order(self):
        assignment = self.assignment

        self.assertTrue(assignment.status == PENDING)
        order_manager.show_order(assignment.order.id, assignment.work_station)

        assignment = OrderAssignment.objects.get(id=assignment.id) # refresh
        self.assertTrue(assignment.status == ASSIGNED and assignment.show_date, "show_order failed")
        self.assertTrue(ORDER.status == PENDING)
        order_manager.accept_order(ORDER, pickup_time=5, station=self.station)
        self.assertTrue((ORDER.status, ORDER.pickup_time, ORDER.station) == (ACCEPTED, 5, self.station), "accept_order failed")

class StationConnectionTest(TestCase):
    """Unit test for the station connection manager."""

    fixtures = ['countries.yaml', 'cities.yaml', 'ordering_test_data.yaml']
    
    def setUp(self):
        setup_testing_env.setup()

    def test_ws_status_notification(self):
        service_url = reverse('ordering.station_controller.notify_ws_status')
        now = datetime.datetime.now()

        # stations not on list do not generate notifications
        for station in Station.objects.all():
            station.show_on_list = True
            station.save()

        # nothing happened
        response = self.client.get(service_url)
        self.assertEqual(response.content, station_controller.OK)

        # new work stations are born
        response = self.client.get(service_url)
        self.assertEqual(response.content, station_controller.OK) # cache was cleared, don't notify

        memcache.set("online_ws", set(["ws"]))
        resuscitate_work_stations()
        response = self.client.get(service_url)
        self.assertEqual(response.content, station_controller.WS_BORN)

        # dead workstation, but not long enough
        dead_ws = WorkStation.objects.all()[0]
        key = get_heartbeat_key(dead_ws)

        memcache.set(key, now - (ALERT_DELTA - datetime.timedelta(minutes=1)))
        response = self.client.get(service_url)
        self.assertEqual(response.content, station_controller.OK)

        # dead workstation, long enough
        memcache.set(key, now - (ALERT_DELTA + datetime.timedelta(minutes=1)))
        response = self.client.get(service_url)
        self.assertEqual(response.content, station_controller.WS_DECEASED)

        # same dead station, don't notify again
        memcache.set(key, now - (ALERT_DELTA + datetime.timedelta(minutes=2)))
        response = self.client.get(service_url)
        self.assertEqual(response.content, station_controller.OK)

        # it's alive!
        memcache.set(key, now)
        response = self.client.get(service_url)
        self.assertEqual(response.content, station_controller.WS_BORN)

        # don't notify
        resuscitate_work_stations()
        response = self.client.get(service_url)
        self.assertEqual(response.content, station_controller.OK)


class DispatcherTest(TestCase):
    """Unit test for the dispatcher ordering logic."""

    fixtures = ['countries.yaml', 'cities.yaml', 'ordering_test_data.yaml']

    def setUp(self):
        setup_testing_env.setup()
        create_passenger()
        create_test_order()
        self.tel_aviv_station = City.objects.get(name=u"תל אביב יפו").stations.all()[0]
        self.jerusalem_station = City.objects.get(name=u"ירושלים").stations.all()[0]
        refresh_order()

    def test_assign_order(self):
        resuscitate_work_stations()
        assignment = assign_order(ORDER)

        self.assertTrue(assignment.station and assignment.work_station)
        self.assertTrue((assignment.order, assignment.status, ORDER.status) == (ORDER, PENDING, ASSIGNED))
        self.assertTrue(assignment.pickup_address_in_ws_lang == u'אלנבי 1, תל אביב יפו')

    def test_choose_workstation_basics(self):
        tel_aviv_ws1 = self.tel_aviv_station.work_stations.all()[0]
        tel_aviv_ws2 = self.tel_aviv_station.work_stations.all()[1]
        jerusalem_ws = self.jerusalem_station.work_stations.all()[0]

        # work stations are dead
        self.assertTrue(choose_workstation(ORDER) is None, "work station are dead, none is expected")

        # live work station but it's in Jerusalem (order is from tel aviv)
        set_heartbeat(jerusalem_ws)
        self.assertTrue(choose_workstation(ORDER) is None, "work station are dead, none is expected")

        # live but don't accept orders
        set_accept_orders_false([tel_aviv_ws1, tel_aviv_ws2])
        resuscitate_work_stations()
        self.assertTrue(choose_workstation(ORDER) is None, "don't accept orders, none is expected.")

        # tel_aviv_ws2 is live and accepts orders
        set_accept_orders_true([tel_aviv_ws2])
        resuscitate_work_stations()
        self.assertTrue(choose_workstation(ORDER) == tel_aviv_ws2, "tel aviv work station 2 is expected.")

    def test_choose_workstation_ignored_and_rejected(self):
        self.run_status_test(IGNORED)
        self.run_status_test(REJECTED)

    def run_status_test(self, status):
        tel_aviv_ws1 = self.tel_aviv_station.work_stations.all()[0]
        tel_aviv_ws2 = self.tel_aviv_station.work_stations.all()[1]

        another_tlv_station = create_another_TLV_station()
        tel_aviv_ws3 = another_tlv_station.work_stations.all()[0]

        resuscitate_work_stations()

        # create an IGNORED/REJECTED assignment by ws1, should get either ws2 or ws3
        assignment = OrderAssignment(order=ORDER, station=self.tel_aviv_station, work_station=tel_aviv_ws1, status=status)
        assignment.save()
        expected_ws_list = [tel_aviv_ws2, tel_aviv_ws3]
        self.assertTrue(tel_aviv_ws1 not in compute_ws_list(ORDER) and choose_workstation(ORDER) in expected_ws_list, "tel aviv ws2/ws3 is expected.")

        # create an IGNORED/REJECTED assignment by ws2, should get ws3
        assignment = OrderAssignment(order=ORDER, station=self.tel_aviv_station, work_station=tel_aviv_ws2, status=status)
        assignment.save()
        refresh_order()
        self.assertTrue(choose_workstation(ORDER) == tel_aviv_ws3, "tel aviv ws2 is expected.")

        # create an IGNORED/REJECTED assignment by ws3, should get None
        assignment = OrderAssignment(order=ORDER, station=another_tlv_station, work_station=tel_aviv_ws3, status=status)
        assignment.save()
        refresh_order()
        self.assertTrue(choose_workstation(ORDER) is None, "no ws is expected.")

    def test_choose_workstation_order(self):
        originating_station = create_another_TLV_station()
        default_station = create_another_TLV_station()
        tel_aviv_station = self.tel_aviv_station

        ORDER.originating_station = originating_station
        ORDER.save()

        PASSENGER.default_station = default_station
        PASSENGER.save()

        resuscitate_work_stations()

        # round trip, in the following order
        for station in [originating_station, default_station, tel_aviv_station]:
            ws = choose_workstation(ORDER)
            self.assertTrue(ws.station == station, "wrong station order")

        # order should return to originating_station
        ws = choose_workstation(ORDER)
        self.assertTrue(ws.station == originating_station, "originating station is expected")

    def test_dispatcher_sort_by_distance(self):
        tel_aviv_station = self.tel_aviv_station
        resuscitate_work_stations()
        self.assertEqual(choose_workstation(ORDER).station, tel_aviv_station)

        refresh_order()
        
        another_station = create_another_TLV_station() # create a closer station to order
        resuscitate_work_stations()

        self.assertEqual(choose_workstation(ORDER).station, another_station)
        self.assertEqual(choose_workstation(ORDER).station, tel_aviv_station)


    def test_default_station(self):
        tel_aviv_station = self.tel_aviv_station
        default_station = create_another_TLV_station()

        PASSENGER.default_station = default_station
        PASSENGER.save()

        # resuscitate work stations and order
        resuscitate_work_stations()
        self.assertTrue(choose_workstation(ORDER).station == default_station, "default station is expected.")

        # check default station overrides last assignment date criteria
        tel_aviv_station.last_assignment_date = datetime.datetime.now()
        tel_aviv_station.save()
        refresh_order()
        self.assertTrue(choose_workstation(ORDER).station == default_station, "default station is expected")

    def test_originating_station(self):
        global PASSENGER
        tel_aviv_station = self.tel_aviv_station
        originating_station = create_another_TLV_station()

        ORDER.originating_station = originating_station
        ORDER.save()

        # set the originating station
        self.client.post(reverse('ordering.order_manager.book_order'), data={"order_id": ORDER.id})
        PASSENGER = Passenger.objects.get(id=PASSENGER.id) # refresh passenger
        self.assertTrue(PASSENGER.originating_station == originating_station, "PASSENGER.originating_station should be tel_aviv_station and not %s" % PASSENGER.originating_station)

        # resuscitate work stations and order
        resuscitate_work_stations()
        self.assertTrue(choose_workstation(ORDER).station == originating_station, "originating station is expected")

        # check originating station overrides last assignment date criteria
        tel_aviv_station.last_assignment_date = datetime.datetime.now()
        tel_aviv_station.save()
        refresh_order()
        self.assertTrue(choose_workstation(ORDER).station == originating_station, "originating station is expected")

    def test_same_default_and_originating_station(self):
        # test same originating and default stations results in one assignment
        global PASSENGER
        global ORDER
        station = create_another_TLV_station()
        ORDER.originating_station = PASSENGER.default_station = station
        ORDER.save()
        PASSENGER.save()

        resuscitate_work_stations()
        ws_list = compute_ws_list(ORDER)
        count = ws_list.count(station.work_stations.all()[0])
        self.assertTrue(count == 1, "originating (==default) station should appear exactly once (got %d)" % count)

class PricingTest(TestCase):
    """
    Unit test for pricing algorithm.
    """
    fixtures = ['countries.yaml', 'cities.yaml']

    def setUp(self):
        # init Israel test
        self.IL = Country.objects.filter(code="IL").get()
        setup_israel_meter_and_extra_charge_rules()
        self.phone_order_price = self.IL.extra_charge_rules.get(rule_name=IsraelExtraCosts.PHONE_ORDER).cost
        self.t, self.d = 768, 4110

    def test_meter_cost(self):
        logging.info("Testing meter cost estimation, with estimated duration: %d & estimated distance: %d" % (self.t, self.d))
        IL = self.IL
        t, d = self.t, self.d
        
        expected_type = CostType.METER
        extras = [IsraelExtraCosts.NATBAG_AIRPORT, IsraelExtraCosts.KVISH_6]
        extras_cost = sum([IL.extra_charge_rules.get(rule_name=extra).cost for extra in extras])

        # tariff 1 test
        expected_cost = calculate_tariff(t, d, tariff1_dict) + self.phone_order_price

        cost, type = estimate_cost(t, d, IL.code, day=1,time=datetime.time(05, 30, 00))
        self.assertEqual(type, expected_type)
        self.assertAlmostEqual(cost, expected_cost, places=2, msg="tariff 1 estimation failed: %d (expected %d)" % (cost, expected_cost))

        cost, type = estimate_cost(t, d, IL.code, day=1, time=datetime.time(20, 59, 59))
        self.assertEqual(type, expected_type)
        self.assertAlmostEqual(cost, expected_cost, places=2, msg="tariff 1 estimation failed: %d (expected %d)" % (cost, expected_cost))

        cost, type = estimate_cost(t, d, IL.code, day=6, time=datetime.time(16, 59, 59))
        self.assertEqual(type, expected_type)
        self.assertAlmostEqual(cost, expected_cost, places=2, msg="Friday estimation failed: %d (expected %d)" % (cost, expected_cost))

        expected_cost += extras_cost
        cost, type = estimate_cost(t, d, IL.code, time=datetime.time(12, 00), extras=extras)
        self.assertEqual(type, expected_type)
        self.assertAlmostEqual(cost, expected_cost, places=2, msg="tariff 1 + extras' estimation failed: %d (expected %d)" % (cost, expected_cost))

        # tariff2 test
        expected_cost = calculate_tariff(t, d, tariff2_dict) + self.phone_order_price

        cost, type = estimate_cost(t, d, IL.code, day=1, time=datetime.time(21, 00, 00))
        self.assertEqual(type, expected_type)
        self.assertAlmostEqual(cost, expected_cost, places=2, msg="tariff 2 estimation failed: %d (expected %d)" % (cost, expected_cost))

        cost, type = estimate_cost(t, d, IL.code, day=1, time=datetime.time(05, 29, 59))
        self.assertEqual(type, expected_type)
        self.assertAlmostEqual(cost, expected_cost, places=2, msg="tariff 2 estimation failed: %d (expected %d)" % (cost, expected_cost))

        cost, type = estimate_cost(t, d, IL.code, day=6, time=datetime.time(17, 00, 00))
        self.assertEqual(type, expected_type)
        self.assertAlmostEqual(cost, expected_cost, places=2, msg="Friday estimation failed: %d (expected %d)" % (cost, expected_cost))

        cost, type = estimate_cost(t, d, IL.code, day=7, time=datetime.time(23, 59, 59))
        self.assertEqual(type, expected_type)
        self.assertAlmostEqual(cost, expected_cost, places=2, msg="Saturday estimation failed: %d (expected %d)" % (cost, expected_cost))

        expected_cost += extras_cost
        cost, type = estimate_cost(t, d, IL.code, time=datetime.time(22, 00), extras=extras)
        self.assertEqual(type, expected_type)
        self.assertAlmostEqual(cost, expected_cost, places=2, msg="tariff 2 + extras' estimation failed: %d (expected %d)" % (cost, expected_cost))

    def test_flat_rate_cost(self):
        IL = self.IL
        t, d = self.t, self.d
        city_a = City.objects.get(name="תל אביב יפו")
        city_b = City.objects.get(name="אור יהודה")
        add_flat_rate_rule(country=IL, from_city=city_a, to_city=city_b, fixed_cost_tariff_1=66, fixed_cost_tariff_2=70)

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
