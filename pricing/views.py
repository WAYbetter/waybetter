from django.shortcuts import render_to_response
from django.utils import simplejson
from google.appengine.api.channel import channel
from google.appengine.ext.deferred import deferred
from common.decorators import mute_logs
from common.models import CityArea
from django.contrib.admin.views.decorators import staff_member_required
from common.signals import  async_computation_failed_signal, async_computation_completed_signal
from common.tz_support import to_js_date
from common.util import split_to_tuples, get_uuid
from django.template.context import RequestContext
from sharing.models import HotSpot
import datetime
import logging

@staff_member_required
def hotspot_pricing_overview(request, hotspot_id):
    hotspot = HotSpot.by_id(hotspot_id)
    channel_id = get_uuid()
    token = channel.create_channel(channel_id)

#    async_computation_submitted_signal.send(sender="hotspot_pricing_overview", channel_id=channel_id)
    deferred.defer(_async_calc_hotspot_pricing_overview, hotspot, channel_id=channel_id, token=token)

    return render_to_response("hotspot_pricing_overview.html", locals(), context_instance=RequestContext(request))


def _async_calc_hotspot_pricing_overview(hotspot, channel_id, token):
    data = None
    try:
        data = _calc_hotspot_pricing_overview(hotspot, channel_id)
    except Exception:
        async_computation_failed_signal.send(sender="hotspot_pricing_overview", channel_id=channel_id)

    from common.views import async_computation_complete_handler
    async_computation_completed_signal.send(sender="hotspot_pricing_overview", channel_id=channel_id, data=data, token=token)

@mute_logs(logging.ERROR)
def _calc_hotspot_pricing_overview(hotspot, client_id):
    # data = [ {day1_series}, {day2_series}, ... ]
    # day_series = { title: str, data: [ {ca1_series}, {ca2_series}, ... ] }
    # ca_series = { label: str, data: [ [x1,y1], [x2,y2], ... ]} - a flot series object
    data = []

    days_ahead = 1
    dates = [datetime.date.today() + datetime.timedelta(days=i) for i in range(0, days_ahead)]

    num_seats = 1
    city_areas = CityArea.objects.all()

    for day in dates:
        day_strftime = day.strftime("%A %d/%m/%y")

        times = hotspot.get_times_for_day(day=day)
        if not times:
            logging.info("no intervals on %s" % day_strftime)
            continue

        ca_series_list = []
        ca_count = city_areas.count()
        ca_idx = 0
        for ca in city_areas:
            ca_idx +=1
            channel.send_message(client_id, simplejson.dumps(
                    {'status': 'processing', 'text': '%s: %s processing %s of %s' % (day_strftime, ca.name, ca_idx, ca_count)}))

            # hack: get a point inside the city area
            itr = split_to_tuples(ca.points, 2)
            lat, lon = 0, 0
            while not ca.contains(lat, lon):
                try:
                    lat, lon = itr.next()
                except StopIteration:
                    logging.error("could not find a point inside %s" % ca.name)
                    break

            points = []
            for t in times:
                price = hotspot.get_sharing_price(lat, lon, day, t, num_seats=num_seats)
                if price:
                    dt = datetime.datetime.combine(day, t)
                    points.append([int(to_js_date(dt)), price])

            if points:
                ca_series = {
                    "data": points,
                    "label": ca.name,
                    "color": ca.color
                }
                ca_series_list.append(ca_series)

        if ca_series_list:
            day_series = {
                'title': day_strftime,
                'id': "%s_%s" % (day.month, day.day),
                'data': ca_series_list
            }
            data.append(day_series)

    return data