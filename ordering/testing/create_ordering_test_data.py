# -*- coding: utf-8 -*-

from django.core import serializers
from django.contrib.auth.models import User

from common.models import Country, City
from ordering.models import Passenger, Station, WorkStation

OUTPUT_FILE = "/home/amir/dev/data/ordering_test_data.yaml"

USER_NAMES = ['test_user', 'test_user_no_passenger']
STATION_NAMES = ['test_station_1', 'test_station_2']
WS_NAMES = ['test_ws_1','test_ws_2', 'test_ws_3']

def create_test_users():
    User.objects.all().exclude(username='waybetter_admin').delete()

    for user_name in USER_NAMES + STATION_NAMES + WS_NAMES:
        user = User()
        user.username = user_name
        user.set_password(user_name)
        user.save()

def create_test_stations():
    Station.objects.all().delete()

    # one in Tel Aviv
    station = Station()
    station_name = STATION_NAMES[0]
    station.name = station_name
    station.user = User.objects.get(username=station_name)
    station.number_of_taxis = 5
    station.country = Country.objects.filter(code="IL").get()
    station.city = City.objects.get(name="תל אביב יפו")
    station.address = 'דיזנגוף 99 תל אביב יפו'
    station.lat = 32.07938
    station.lon = 34.773896
    station.save()

    # and one in Jerusalem
    station = Station()
    station_name = STATION_NAMES[1]
    station.name = station_name
    station.user = User.objects.get(username=station_name)
    station.number_of_taxis = 5
    station.country = Country.objects.filter(code="IL").get()
    station.city = City.objects.get(name="ירושלים")
    station.address = 'בן יהודה 35 ירושלים'
    station.lat = 31.780725
    station.lon = 35.214161
    station.save()

def create_test_work_stations():
    WorkStation.objects.all().delete()
    # one for test_station_1
    station = Station.objects.get(name=STATION_NAMES[0])
    ws_name = WS_NAMES[0]
    ws = WorkStation()
    ws.user = User.objects.get(username=ws_name)
    ws.station = station
    ws.was_installed = True
    ws.accept_orders = True
    ws.save()

    # and two more for test_station_2
    station = Station.objects.get(name=STATION_NAMES[1])
    ws1_name, ws2_name = WS_NAMES[1], WS_NAMES[2]
    ws1, ws2 = WorkStation(), WorkStation()
    ws1.user, ws2.user = User.objects.get(username=ws1_name), User.objects.get(username=ws2_name)
    ws1.station = ws2.station = station
    ws1.was_installed = ws2.was_installed= True
    ws1.accept_orders = ws2.accept_orders = True
    ws1.save()
    ws2.save()

def create():
  out = open(OUTPUT_FILE, 'w')

  all_objects = []

  create_test_users()
  all_objects += list(User.objects.all())

  create_test_stations()
  all_objects += list(Station.objects.all())

  create_test_work_stations()
  all_objects += list(WorkStation.objects.all())
    
  data = serializers.serialize("yaml", all_objects)
  out.write(data)
  out.close()