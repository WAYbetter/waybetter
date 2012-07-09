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
from ordering.decorators import NOT_A_PASSENGER
from ordering.pricing import estimate_cost, IsraelExtraCosts, CostType, setup_israel_meter_and_extra_charge_rules, tariff1_dict, tariff2_dict
from ordering.rules_controller import add_flat_rate_rule

from testing import setup_testing_env
from testing.meter_calculator import calculate_tariff

import logging
import datetime
import os

os.environ["TZ"] = "UTC"
ISRAEL_ID = 12
TLV_ID = 1604
FAR_AWAY_LAT = -76.936516
FAR_AWAY_LON = -12.234392
ORDER_DATA = {
    "from_city": TLV_ID,
    "from_country": ISRAEL_ID,
    "from_geohash": u'swnvcbg7d23u',
    "from_lat": u'32.073666',
    "from_lon": u'34.765472',
    "from_raw": u'Allenby 1, Tel Aviv Yafo',
    "from_street_address": u'Allenby',
    "from_house_number": u'1',
    "geocoded_from_raw": u'Allenby 1, Tel Aviv Yafo',
    "to_city": TLV_ID,
    "to_country": ISRAEL_ID,
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

def create_passenger():
    test_user = User.objects.get(username='test_user')
    passenger = Passenger()
    passenger.user = test_user
    passenger.country = Country.objects.filter(code="IL").get()
    passenger.save()

    return passenger

def create_test_order(passenger=None):
    if not passenger:
        passenger = create_passenger()

    form = OrderForm(data=ORDER_DATA, passenger=passenger)
    order = form.save()
    order.passenger = passenger
    order.save()

    return order

def create_another_TLV_station(num_of_ws=1):
    # create another station in TLV
    tel_aviv = City.objects.get(name=u'תל אביב יפו')
    station_name = 'tel_aviv_%d' % (Station.objects.filter(city=tel_aviv).count()+1)
    ws_names = []
    for i in range(num_of_ws):
        ws_names.append("%s_%s%d" % (station_name, "ws", i+1))

    station = None
    for user_name in [station_name] + ws_names:
        user = User(username=user_name)
        user.set_password(user_name)
        user.save()

        if user_name == station_name:
            station = Station(name=station_name, user=user, number_of_taxis=5,
                                    country=Country.objects.filter(code="IL").get(), city=City.objects.get(name="תל אביב יפו"), address='גאולה 12', lat=32.071838, lon=34.766906)
            station.save()
        else:
            ws = WorkStation(user=user, station=station, was_installed = True, accept_orders = True)
            ws.save()

    return station

def refresh_order(order):
    order = Order.objects.get(id=order.id)
    memcache.set('ws_list_for_order_%s' % order.id, [])
    memcache.set('ws_list_index_for_order_%s' % order.id, 0)
    return order

def resuscitate_work_stations():
    for ws in WorkStation.objects.all():
        ws.is_online = True
        ws.save()


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

class BasicTests(TestCase):
    fixtures = ['countries.yaml', 'cities.yaml', 'ordering_test_data.yaml']

    def setUp(self):
        setup_testing_env.setup()

    def test_distance_from_station(self):
        station = Station.objects.all()[0]

        # valid distance from a point
        self.assertTrue(station.is_in_valid_distance(from_lat=station.lat, from_lon=station.lon))
        self.assertTrue(station.is_in_valid_distance(to_lat=station.lat, to_lon=station.lon))
        self.assertTrue(station.is_in_valid_distance(from_lat=station.lat, from_lon=station.lon, to_lat=station.lat, to_lon=station.lon))

        # valid distance from an order pickup
        order = create_test_order()
        order.from_lat, order.from_lon = station.lat, station.lon
        order.to_lat, order.to_lon = None, None
        order.save()
        self.assertTrue(station.is_in_valid_distance(order=order))

        # valid distance from an order dropoff
        order.from_lat, order.from_lon = FAR_AWAY_LAT, FAR_AWAY_LON
        order.to_lat, order.to_lon = station.lat, station.lon
        order.save()
        self.assertTrue(station.is_in_valid_distance(order=order))

        # not in valid distance
        self.assertFalse(station.is_in_valid_distance(from_lat=FAR_AWAY_LAT, from_lon=FAR_AWAY_LON))
        self.assertFalse(station.is_in_valid_distance(to_lat=FAR_AWAY_LAT, to_lon=FAR_AWAY_LON))
        self.assertFalse(station.is_in_valid_distance(from_lat=FAR_AWAY_LAT, from_lon=FAR_AWAY_LON, to_lat=FAR_AWAY_LAT, to_lon=FAR_AWAY_LON))

        order.from_lat, order.from_lon = FAR_AWAY_LAT, FAR_AWAY_LON
        order.to_lat, order.to_lon = FAR_AWAY_LAT, FAR_AWAY_LON
        order.save()
        self.assertFalse(station.is_in_valid_distance(order=order))

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

        passenger = create_passenger()

        # good order
        form = OrderForm(data=ORDER_DATA, passenger=passenger)
        self.assertTrue(form.is_valid(), "Form should pass validation.")

        # bad orders
        for dict_name in bad_data:
            bad_order = ORDER_DATA.copy()
            bad_order.update(bad_data[dict_name])
            form = OrderForm(data=bad_order, passenger=passenger)
            self.assertFalse(form.is_valid(), "Form should fail validation: %s" % dict_name)


class OrderManagerTest(TestCase):
    """Unit test for the logic of the order manager."""

    fixtures = ['countries.yaml', 'cities.yaml', 'ordering_test_data.yaml']

    def setUp(self):
        setup_testing_env.setup()
        self.passenger = create_passenger()
        self.order = create_test_order()
        self.station = Station.objects.get(name='test_station_1')
        self.work_station = WorkStation.objects.filter(station=self.station)[0]
        self.assignment = OrderAssignment(order=self.order, station=self.station, work_station=self.work_station)
        self.assignment.save()
        # TODO_WB: remove when we have new fixtures
        phone1 = Phone(local_phone=u'1234567', station=self.station)
        phone1.save()
        phone2 = Phone(local_phone=u'0000000', station=self.station)
        phone2.save()

    def test_book_order(self):
        order = self.order

        response = self.client.post(reverse('ordering.order_manager.book_order'), data={"order_id": order.id})

        # working stations are dead, assignment should fail
        self.assertTrue((response.content, response.status_code) == (NO_MATCHING_WORKSTATIONS_FOUND, 200), "Assignment should fail: workstations are dead")

        # resuscitate work stations and try again
        resuscitate_work_stations()
        response = self.client.post(reverse('ordering.order_manager.book_order'), data={"order_id": order.id})
        self.assertTrue((response.content, response.status_code) == (ORDER_HANDLED, 200), "Assignment should succeed: workstations are live")

        # timed out order
        order = refresh_order(order)
        order.create_date = datetime.datetime.now() - datetime.timedelta(seconds=ORDER_HANDLE_TIMEOUT+1)
        order.save()
        response = self.client.post(reverse('ordering.order_manager.book_order'), data={"order_id": order.id})
        self.assertTrue((response.content, response.status_code) == (ORDER_TIMEOUT, 200), "Assignment should fail: order time out")

    def test_update_future_pickup(self):
        order = self.order
        self.assertTrue(order.future_pickup == False, "new orders should have future_pickup == False by default")
        self.client.post(reverse('ordering.order_manager.update_future_pickup'), data={"order_id": order.id})
        self.assertTrue(order.future_pickup == False, "future_pickup changed from False to True")

        order.future_pickup = True
        order.save()
        self.client.post(reverse('ordering.order_manager.update_future_pickup'), data={"order_id": order.id})
        self.assertTrue(order.future_pickup == True, "future_pickup should changed to True")

    def test_redispatch_orders(self):
        assignment = self.assignment

        # NOT_TAKEN assignment
        assignment.create_date = datetime.datetime.now() - datetime.timedelta(seconds=ORDER_TEASER_TIMEOUT+1)
        assignment.save()
        self.client.post(reverse('ordering.order_manager.redispatch_pending_orders'), data={"order_assignment_id": assignment.id})
        assignment = OrderAssignment.objects.get(id=assignment.id) # refresh
        self.assertTrue(assignment.status == NOT_TAKEN, "assignment should be marked as not taken.")

        # IGNORED assignment
        assignment.change_status(new_status=ASSIGNED)
        assignment.create_date = datetime.datetime.now() - datetime.timedelta(seconds=ORDER_ASSIGNMENT_TIMEOUT+1)
        assignment.save()
        self.client.post(reverse('ordering.order_manager.redispatch_ignored_orders'), data={"order_assignment_id": assignment.id})
        assignment = OrderAssignment.objects.get(id=assignment.id) # refresh
        self.assertTrue(assignment.status == IGNORED, "assignment should be marked as ignored.")

    def test_show_and_accept_order(self):
        order = self.order
        assignment = self.assignment
        order.change_status(PENDING, ASSIGNED)

        self.assertTrue(assignment.status == PENDING)
        order_manager.show_order(assignment.order.id, assignment.work_station)

        assignment = OrderAssignment.objects.get(id=assignment.id) # refresh
        self.assertTrue(assignment.status == ASSIGNED and assignment.show_date, "show_order failed")
        order_manager.accept_order(order, pickup_time=5, station=self.station)
        self.assertTrue((order.status, order.pickup_time, order.station) == (ACCEPTED, 5, self.station), "accept_order failed")

class DispatcherTest(TestCase):
    """Unit test for the dispatcher ordering logic."""

    fixtures = ['countries.yaml', 'cities.yaml', 'ordering_test_data.yaml']

    def setUp(self):
        setup_testing_env.setup()
        self.passenger = create_passenger()
        self.order = create_test_order()
        self.tel_aviv_station = City.objects.get(name=u"תל אביב יפו").stations.all()[0]
        self.jerusalem_station = City.objects.get(name=u"ירושלים").stations.all()[0]
        refresh_order(self.order)

    def test_assign_order(self):
        order = self.order
        resuscitate_work_stations()
        assignment = assign_order(order)

        self.assertTrue(assignment.station and assignment.work_station)
        self.assertTrue((assignment.order, assignment.status, order.status) == (order, PENDING, ASSIGNED))
        self.assertTrue(assignment.pickup_address_in_ws_lang == u'אלנבי 1, תל אביב יפו')

    def test_choose_workstation_basics(self):
        order = self.order

        tel_aviv_ws1 = self.tel_aviv_station.work_stations.all()[0]
        tel_aviv_ws2 = self.tel_aviv_station.work_stations.all()[1]
        jerusalem_ws = self.jerusalem_station.work_stations.all()[0]

        # work stations are dead
        self.assertTrue(choose_workstation(order) is None, "work station are dead, none is expected")

        # live work station but it's in Jerusalem (order is from tel aviv)
        jerusalem_ws.is_online = True
        jerusalem_ws.save()
        self.assertTrue(choose_workstation(order) is None, "work station are dead, none is expected")
        refresh_order(order)

        # live but don't accept orders
        set_accept_orders_false([tel_aviv_ws1, tel_aviv_ws2])
        resuscitate_work_stations()
        self.assertTrue(choose_workstation(order) is None, "don't accept orders, none is expected.")
        refresh_order(order)

        # tel_aviv_ws2 is live and accepts orders
        set_accept_orders_true([tel_aviv_ws2])
        resuscitate_work_stations()
        self.assertTrue(choose_workstation(order) == tel_aviv_ws2, "tel aviv work station 2 is expected.")
        refresh_order(order)

    def test_choose_workstation_ignored(self):
        self._run_ignored_or_rejected_test(IGNORED)

    def test_choose_workstation_rejected(self):
        self._run_ignored_or_rejected_test(REJECTED)

    def _run_ignored_or_rejected_test(self, status):
        order = self.order

        tel_aviv = self.tel_aviv_station
        tel_aviv_ws1 = tel_aviv.work_stations.all()[0]
        tel_aviv_ws2 = tel_aviv.work_stations.all()[1]

        tel_aviv_2 = create_another_TLV_station()
        tel_aviv_ws3 = tel_aviv_2.work_stations.all()[0]

        resuscitate_work_stations()

        # create an IGNORED/REJECTED assignment by first station (ws1, ws2), should get ws3
        assignment = OrderAssignment(order=order, station=tel_aviv, work_station=tel_aviv_ws1, status=status)
        assignment.save()
        ws_list = compute_ws_list(order)
        self.assertTrue(tel_aviv_ws1 not in ws_list and tel_aviv_ws2 not in ws_list, "this station ignored the order.")

        next_ws = choose_workstation(order)
        self.assertTrue(next_ws == tel_aviv_ws3, "tel aviv ws3 is expected.")

        # create an IGNORED/REJECTED assignment by ws3, should get None
        assignment = OrderAssignment(order=order, station=tel_aviv_2, work_station=tel_aviv_ws3, status=status)
        assignment.save()
        refresh_order(order)
        self.assertTrue(choose_workstation(order) is None, "no ws is expected.")

    def test_choose_workstation_order(self):
        order = self.order
        resuscitate_work_stations()

        station1 = self.tel_aviv_station # should have 2 work stations (from fixtures)
        station2 = create_another_TLV_station(num_of_ws=2)

        resuscitate_work_stations()
        
        ws_list = compute_ws_list(order)

        # stations should alternate
        self.assertTrue(ws_list[0].station == ws_list[2].station and ws_list[1].station == ws_list[3].station, "stations should alternate")

        # work stations should alternate
        self.assertTrue(ws_list[0] != ws_list[2] and ws_list[1] != ws_list[3], "work stations should alternate")

        #
        # scenario: station x -> station y (reject) -> station x
        #
        order = create_test_order()
        first_ws = choose_workstation(order)
        second_ws = choose_workstation(order)

        assignment = OrderAssignment(order=order, station=second_ws.station, work_station=second_ws, status=REJECTED)
        assignment.save()
        refresh_order(order)

        third_ws = choose_workstation(order)

        self.assertTrue(third_ws.station == first_ws.station)

        #
        # scenario: station x -> station y (not taken) -> station x -> station y other ws
        #
        order = create_test_order()
        first_ws = choose_workstation(order)
        second_ws = choose_workstation(order)

        assignment = OrderAssignment(order=order, station=second_ws.station, work_station=second_ws, status=NOT_TAKEN)
        assignment.save()

        third_ws = choose_workstation(order)
        fourth_ws = choose_workstation(order)

        self.assertTrue(second_ws.station == fourth_ws.station and second_ws != fourth_ws)


    def test_choose_workstation_order_default_and_originating(self):
        """
        Test the order when we have a default and an originating station
        """
        order = self.order
        passenger = self.passenger

        tel_aviv_station = self.tel_aviv_station # should have 2 work stations (from fixtures)
        default_station = create_another_TLV_station(num_of_ws=2)
        originating_station = create_another_TLV_station(num_of_ws=2)

        # set originating and default station
        order.originating_station = originating_station
        order.save()

        passenger.default_station = default_station
        passenger.save()
        order.passenger = passenger
        order.save()

        resuscitate_work_stations()

        # round trip, in the following order
        for station in [originating_station]*2 + [default_station]*2 + [tel_aviv_station]*2:
            ws = choose_workstation(order)
            self.assertTrue(ws.station == station, "wrong station order: expected %s got %s" % (station, ws.station))

        # order should return to originating_station
        ws = choose_workstation(order)
        self.assertTrue(ws.station == originating_station, "originating station is expected")

    def test_dispatcher_sort_by_distance(self):
        order = self.order
        tel_aviv_station = self.tel_aviv_station
        resuscitate_work_stations()
        self.assertEqual(choose_workstation(order).station, tel_aviv_station)

        refresh_order(order)
        
        another_station = create_another_TLV_station() # create a closer station to order
        resuscitate_work_stations()

        self.assertEqual(choose_workstation(order).station, another_station)
        self.assertEqual(choose_workstation(order).station, tel_aviv_station)


    def test_default_station(self):
        order = self.order
        passenger = self.passenger
        tel_aviv_station = self.tel_aviv_station
        default_station = create_another_TLV_station()

        passenger.default_station = default_station
        passenger.save()
        order.passenger = passenger
        order.save()

        # resuscitate work stations and order
        resuscitate_work_stations()
        self.assertTrue(choose_workstation(order).station == default_station, "default station is expected.")

        # check default station overrides last assignment date criteria
        tel_aviv_station.last_assignment_date = datetime.datetime.now()
        tel_aviv_station.save()
        refresh_order(order)
        self.assertTrue(choose_workstation(order).station == default_station, "default station is expected")

    def test_originating_station(self):
        passenger = self.passenger
        order = create_test_order(passenger)

        tel_aviv_station = self.tel_aviv_station
        originating_station = create_another_TLV_station()

        order.originating_station = originating_station
        order.save()

        # set the originating station
        self.client.post(reverse('ordering.order_manager.book_order'), data={"order_id": order.id})
        passenger = Passenger.objects.get(id=passenger.id) # refresh passenger
        self.assertTrue(passenger.originating_station == originating_station, "passenger.originating_station should be tel_aviv_station and not %s" % passenger.originating_station)
        refresh_order(order)
        
        # resuscitate work stations and order
        resuscitate_work_stations()
        self.assertTrue(choose_workstation(order).station == originating_station, "originating station is expected")

        # check originating station overrides last assignment date criteria
        tel_aviv_station.last_assignment_date = datetime.datetime.now()
        tel_aviv_station.save()
        refresh_order(order)
        self.assertTrue(choose_workstation(order).station == originating_station, "originating station is expected")


        # test same originating and default stations results in one assignment
        passenger.default_station = originating_station
        passenger.save()
        order = refresh_order(order)
        order.passenger = passenger
        order.save()
        self.assertTrue(order.passenger.default_station == order.originating_station, "originating and default stations are not the same")

        resuscitate_work_stations()
        ws_list = compute_ws_list(order)
        count = ws_list.count(originating_station.work_stations.all()[0])
        self.assertTrue(count == 1, "originating (==default) station should appear exactly once (got %d)" % count)

    def test_confine_to_station(self):
        passenger = self.passenger
        order = create_test_order(passenger)
        confining_station = create_another_TLV_station()

        order.confining_station = confining_station
        order.save()

        # order, should get confining station
        resuscitate_work_stations()
        self.assertTrue(choose_workstation(order).station == confining_station, "confining station is expected")

        # order out of confining station service radius, should still assign the order
        order.from_lat, order.from_lon = FAR_AWAY_LAT, FAR_AWAY_LON
        order.to_lat, order.to_lon = None, None
        order.save()
        refresh_order(order)
        self.assertTrue(choose_workstation(order).station == confining_station, "confining station is expected")

        # create a REJECTED assignment by confining_station, should get None
        assignment = OrderAssignment(order=order, station=confining_station, work_station=confining_station.work_stations.all()[0], status=REJECTED)
        assignment.save()
        refresh_order(order)
        self.assertTrue(choose_workstation(order) is None, "no ws is expected.")

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
        expected_cost_tariff1 = calculate_tariff(t, d, tariff1_dict) + self.phone_order_price
        expected_cost_tariff2 = calculate_tariff(t, d, tariff2_dict) + self.phone_order_price
        extras = [IsraelExtraCosts.NATBAG_AIRPORT, IsraelExtraCosts.KVISH_6]
        extras_cost = sum([IL.extra_charge_rules.get(rule_name=extra).cost for extra in extras])

        # tariff 1 test
        cost, type = estimate_cost(t, d, IL.code, day=1,time=datetime.time(05, 30, 00))
        self.assertEqual(type, expected_type)
        self.assertAlmostEqual(cost, expected_cost_tariff1, places=2, msg="tariff 1 estimation failed: %d (expected %d)" % (cost, expected_cost_tariff1))

        cost, type = estimate_cost(t, d, IL.code, day=1, time=datetime.time(20, 59, 59))
        self.assertEqual(type, expected_type)
        self.assertAlmostEqual(cost, expected_cost_tariff1, places=2, msg="tariff 1 estimation failed: %d (expected %d)" % (cost, expected_cost_tariff1))

        cost, type = estimate_cost(t, d, IL.code, day=6, time=datetime.time(16, 59, 59))
        self.assertEqual(type, expected_type)
        self.assertAlmostEqual(cost, expected_cost_tariff1, places=2, msg="Friday estimation failed: %d (expected %d)" % (cost, expected_cost_tariff1))

        cost, type = estimate_cost(t, d, IL.code, time=datetime.time(12, 00), extras=extras)
        self.assertEqual(type, expected_type)
        self.assertAlmostEqual(cost, expected_cost_tariff1 + extras_cost, places=2, msg="tariff 1 + extras' estimation failed: %d (expected %d)" % (cost, expected_cost_tariff1 + extras_cost))

        # tariff2 test
        cost, type = estimate_cost(t, d, IL.code, day=1, time=datetime.time(21, 00, 00))
        self.assertEqual(type, expected_type)
        self.assertAlmostEqual(cost, expected_cost_tariff2, places=2, msg="tariff 2 estimation failed: %d (expected %d)" % (cost, expected_cost_tariff2))

        cost, type = estimate_cost(t, d, IL.code, day=1, time=datetime.time(05, 29, 59))
        self.assertEqual(type, expected_type)
        self.assertAlmostEqual(cost, expected_cost_tariff2, places=2, msg="tariff 2 estimation failed: %d (expected %d)" % (cost, expected_cost_tariff2))

        cost, type = estimate_cost(t, d, IL.code, day=6, time=datetime.time(17, 00, 00))
        self.assertEqual(type, expected_type)
        self.assertAlmostEqual(cost, expected_cost_tariff2, places=2, msg="Friday estimation failed: %d (expected %d)" % (cost, expected_cost_tariff2))

        cost, type = estimate_cost(t, d, IL.code, day=7, time=datetime.time(23, 59, 59))
        self.assertEqual(type, expected_type)
        self.assertAlmostEqual(cost, expected_cost_tariff2, places=2, msg="Saturday estimation failed: %d (expected %d)" % (cost, expected_cost_tariff2))

        cost, type = estimate_cost(t, d, IL.code, time=datetime.time(22, 00), extras=extras)
        self.assertEqual(type, expected_type)
        self.assertAlmostEqual(cost, expected_cost_tariff2 + extras_cost, places=2, msg="tariff 2 + extras' estimation failed: %d (expected %d)" % (cost, expected_cost_tariff2 + extras_cost))

        # friday
        cost, type = estimate_cost(t, d, IL.code, day=6, time=datetime.time(01, 00, 00))
        self.assertEqual(type, expected_type)
        self.assertAlmostEqual(cost, expected_cost_tariff2, places=2, msg="Friday tariff2 failed: %d (expected %d)" % (cost, expected_cost_tariff2))

        cost, type = estimate_cost(t, d, IL.code, day=6, time=datetime.time(06, 00, 00))
        self.assertEqual(type, expected_type)
        self.assertAlmostEqual(cost, expected_cost_tariff1, places=2, msg="Friday tariff1 failed: %d (expected %d)" % (cost, expected_cost_tariff1))

        cost, type = estimate_cost(t, d, IL.code, day=6, time=datetime.time(17, 01, 00))
        self.assertEqual(type, expected_type)
        self.assertAlmostEqual(cost, expected_cost_tariff2, places=2, msg="Friday sabbath failed: %d (expected %d)" % (cost, expected_cost_tariff2))

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
