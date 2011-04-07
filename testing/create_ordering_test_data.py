# -*- coding: utf-8 -*-

## TODO_WB: this is not in sync with the countries and cities fixtures, should create a script for creating ALL fixtures

from django.core import serializers
from django.contrib.auth.models import User

from common.models import Country, City
from ordering.models import Passenger, Station, WorkStation, Phone

#OUTPUT_FILE = "ordering/fixtures/ordering_test_data.yaml"

USER_NAMES = ['ordering_test_user', 'ordering_test_user_no_passenger']
STATION_NAMES = ['Tel Aviv station', 'Jerusalem station']
WS_NAMES = ['ws1','ws2', 'ws3']

def create_test_users():
    for user_name in USER_NAMES + STATION_NAMES + WS_NAMES:
        user = User()
        user.username = user_name
        user.set_password(user_name)
        user.save()

def create_test_stations():
    # one in Tel Aviv
    station_name = STATION_NAMES[0]

    station = Station()
    station.name = station_name
    station.user = User.objects.get(username=station_name)
    station.number_of_taxis = 5
    station.country = Country.objects.filter(code="IL").get()
    station.city = City.objects.get(name="תל אביב יפו")
    station.address = 'דיזנגוף 99 תל אביב יפו'
    station.lat = 32.07938
    station.lon = 34.773896
    station.save()

    phone = Phone(local_phone=u'1234567', station=station)
    phone.save()

    # and one in Jerusalem
    station_name = STATION_NAMES[1]

    station = Station()
    station.name = station_name
    station.user = User.objects.get(username=station_name)
    station.number_of_taxis = 5
    station.country = Country.objects.filter(code="IL").get()
    station.city = City.objects.get(name="ירושלים")
    station.address = 'בן יהודה 35 ירושלים'
    station.lat = 31.780725
    station.lon = 35.214161
    station.save()

    phone = Phone(local_phone=u'1234567', station=station)
    phone.save()

def create_test_work_stations():
    # two for test_station_1
    station = Station.objects.get(name=STATION_NAMES[0])
    ws1_name, ws2_name = WS_NAMES[0], WS_NAMES[1]
    ws1, ws2 = WorkStation(), WorkStation()
    ws1.user, ws2.user = User.objects.get(username=ws1_name), User.objects.get(username=ws2_name)
    ws1.station = ws2.station = station
    ws1.was_installed = ws2.was_installed= True
    ws1.accept_orders = ws2.accept_orders = True
    ws1.save()
    ws2.save()

    # and one for test_station_2
    station = Station.objects.get(name=STATION_NAMES[1])
    ws_name = WS_NAMES[2]
    ws = WorkStation()
    ws.user = User.objects.get(username=ws_name)
    ws.station = station
    ws.was_installed = True
    ws.accept_orders = True
    ws.save()


def create():
  out = open(OUTPUT_FILE, 'w')

  out.write('# created using create_ordering_data.py\n')

  created_objects = []

  create_test_users()
  created_objects += list(User.objects.filter(username__in=USER_NAMES + STATION_NAMES + WS_NAMES))

  create_test_stations()
  created_objects += list(Station.objects.filter(user__in=created_objects))

  create_test_work_stations()
  created_objects += list(WorkStation.objects.filter(user__in=created_objects))
    
  data = serializers.serialize("yaml", created_objects)
  out.write(data)
  out.close()

  for obj in created_objects:
      obj.delete()
