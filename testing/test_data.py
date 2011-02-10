# -*- coding: utf-8 -*-

from django.http import HttpResponse
from django.contrib.auth.models import User
from ordering.models import Order, Passenger, ACCEPTED, Station, WorkStation
from common.models import Country, City


SELENIUM_USER_NAMES = ['selenium_user', 'selenium_station_user', 'selenium_ws_user']
SELENIUM_PASSENGER = None
SELENIUM_STATION = None

# accounts for social auth
GOOGLE_USERNAME = "tests@waybetter.com"
GOOGLE_PASSWORD = "WB110310"
FACEBOOK_USERNAME = "tests@waybetter.com"
FACEBOOK_PASSWORD = "WB110310"

# WAYbetter account details:
# username: test@waybetter.com
# password: wbtest

def create_selenium_test_data(request):
    """ Create selenium users, passengers, stations and work stations."""

    global SELENIUM_PASSENGER
    global SELENIUM_STATION

    # if selenium data exists, destroy it.
    if User.objects.filter(username__in=SELENIUM_USER_NAMES):
        destroy_selenium_test_data(request)

    # create selenium users
    selenium_user = create_selenium_user("selenium_user", email="test@waybetter.com")
    selenium_station_user = create_selenium_user("selenium_station_user")
    selenium_ws_user = create_selenium_user("selenium_ws_user")

    # create selenium passenger, station and workstation
    SELENIUM_PASSENGER = Passenger(user=selenium_user, country=Country.objects.filter(code="IL").get(), phone="0521234567", phone_verified=True)
    SELENIUM_PASSENGER.save()

    SELENIUM_STATION = Station(name="selenium_station", user=selenium_station_user, number_of_taxis=5, country=Country.objects.filter(code="IL").get(),
                               city=City.objects.get(name="תל אביב יפו"), address='אחד העם 1 תל אביב', lat=32.063325, lon=34.768338)
    SELENIUM_STATION.save()

    selenium_ws = WorkStation(user=selenium_ws_user, station=SELENIUM_STATION, was_installed = True, accept_orders = True)
    selenium_ws.save()

    # create some orders
    create_selenium_dummy_order(u"גאולה 1 תל אביב", u"דיזנגוף 9 תל אביב")
    create_selenium_dummy_order(u"היכל נוקיה", u"דיזנגוף סנטר")

    return HttpResponse("selenium data created")

def destroy_selenium_test_data(request):
    """ Delete selenium users, passengers, stations and work stations."""

    for user in list(User.objects.filter(username__in=SELENIUM_USER_NAMES)):
        try:
            passenger = Passenger.objects.get(user=user)
            Order.objects.filter(passenger=passenger).delete()
            passenger.delete()
        except: pass
        try:
            Station.objects.get(user=user).delete()
        except: pass
        try:
            WorkStation.objects.get(user=user).delete()
        except: pass

        user.delete()
    return HttpResponse("selenium data destroyed")

def create_selenium_user(username, email=None):
    user = User(username=username)
    user.set_password(username)
    if email:
        user.email = email
    user.save()
    return user

def create_selenium_dummy_order(from_raw, to_raw):
    order = Order(
            passenger=SELENIUM_PASSENGER,
            station=SELENIUM_STATION,
            status=ACCEPTED,
            from_city=City.objects.get(name="תל אביב יפו"),
            from_country=Country.objects.get(code="IL"),
            from_geohash=u'gibrish',
            from_lat=u'32',
            from_lon=u'34',
            from_raw=from_raw,
            from_street_address=u'street1',
            to_city=City.objects.get(name="תל אביב יפו"),
            to_country=Country.objects.get(code="IL"),
            to_geohash=u'swnvcbdruxgz',
            to_lat=u'32',
            to_lon=u'34',
            to_raw=to_raw,
            to_street_address=u'street2',
            )
    order.save()

    return order