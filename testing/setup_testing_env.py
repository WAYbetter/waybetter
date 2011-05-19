# -*- coding: utf-8 -*-

import datetime
from django.http import HttpResponse
from django.contrib.auth.models import User
from ordering.models import Order, Passenger, ACCEPTED, Station, WorkStation, Phone
from ordering.util import create_passenger, create_user, safe_delete_user
from common.models import Country, City
from socialauth.models import OpenidProfile
from selenium_helper import SELENIUM_USER_NAME,SELENIUM_STATION_USER_NAME, SELENIUM_WS_USER_NAME,SELENIUM_PASSWORD, SELENIUM_PHONE, SELENIUM_USER_NAMES, SELENIUM_EMAIL, SELENIUM_ADDRESS, SELENIUM_CITY_NAME
SELENIUM_PASSENGER = None
SELENIUM_STATION = None

#import os
#os.environ["DJANGO_SETTINGS_MODULE"] = "settings"

def setup():

    # setup appengine task queue
    import os
    from google.appengine.api import apiproxy_stub_map
    taskqueue_stub = apiproxy_stub_map.apiproxy.GetStub('taskqueue')
    taskqueue_stub._root_path = os.path.join(os.path.dirname(__file__), '..')

def create_selenium_test_data(request):
    """ Create selenium users, passengers, stations and work stations."""

    global SELENIUM_PASSENGER
    global SELENIUM_STATION

    # if selenium data exists, destroy it.
    if User.objects.filter(username__in=SELENIUM_USER_NAMES):
        destroy_selenium_test_data(request)

    # create selenium passenger and station
    selenium_user = create_selenium_user(SELENIUM_USER_NAME)
    SELENIUM_PASSENGER = create_selenium_passenger(selenium_user)
        
    selenium_station_user = create_selenium_user(SELENIUM_STATION_USER_NAME)
    SELENIUM_STATION = create_selenium_station(selenium_station_user)

    # create some orders
    create_selenium_dummy_order(u"גאולה 1 תל אביב", u"דיזנגוף 9 תל אביב")
    create_selenium_dummy_order(u"היכל נוקיה", u"דיזנגוף סנטר")

    return HttpResponse("selenium data created")

def create_selenium_test_station(request):
    """
    For tests in which we do not want a selenium user, only a station.
    """
    selenium_station_user = create_selenium_user(SELENIUM_STATION_USER_NAME)
    selenium_station = create_selenium_station(selenium_station_user)
    return HttpResponse("selenium test station created")

def destroy_selenium_test_data(request):

    # Delete selenium users, passengers, stations and work stations
    for user in User.objects.filter(username__in=SELENIUM_USER_NAMES):
        try:
            passenger = Passenger.objects.get(user=user)
            Order.objects.filter(passenger=passenger).delete()
            passenger.delete()
        except Passenger.DoesNotExist:
            pass
        try:
            Station.objects.get(user=user).delete()
        except Station.DoesNotExist:
            pass
        try:
            WorkStation.objects.get(user=user).delete()
        except WorkStation.DoesNotExist:
            pass

        safe_delete_user(user)

    # user created by socialauth
    try:
        user = User.objects.get(email=SELENIUM_EMAIL)
        safe_delete_user(user)
    except User.DoesNotExist:
        pass
    except User.MultipleObjectsReturned:
        return HttpResponse("error deleting social data")

    return HttpResponse("selenium data destroyed")

def create_selenium_dummy_order(from_raw, to_raw):
    order = Order(
            passenger=SELENIUM_PASSENGER,
            station=SELENIUM_STATION,
            status=ACCEPTED,
            from_city=City.objects.get(name="תל אביב יפו"),
            from_country=Country.objects.get(code="IL"),
            from_geohash=u'swnvcbdruxgz',
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
            create_date=datetime.datetime.now()-datetime.timedelta(hours=1)
            )
    order.save()

    return order

def create_selenium_user(user_name):
    user = create_user(username=user_name, password=SELENIUM_PASSWORD, email=user_name)
    return user

def create_selenium_passenger(user):
    passenger = create_passenger(user=user, country=Country.objects.filter(code="IL").get(), phone=SELENIUM_PHONE)
    return passenger

def create_selenium_station(user):
    selenium_station = Station(name="selenium_station", user=user, number_of_taxis=5, country=Country.objects.filter(code="IL").get(),
                           city=City.objects.get(name=SELENIUM_CITY_NAME), address=SELENIUM_ADDRESS, lat=32.105137, lon=35.198071, license_number="1234", postal_code='1234',
                           website_url="http://selenium.waybetter.com")
    selenium_station.save()

    phone = Phone(local_phone=SELENIUM_PHONE, station=selenium_station)
    phone.save()

#    selenium_station.build_workstations()
    
    return selenium_station