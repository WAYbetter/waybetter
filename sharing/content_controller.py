# This Python file uses the following encoding: utf-8
from django.shortcuts import render_to_response
from common.decorators import force_lang
from common.models import City
from django.template.context import RequestContext
from common.util import custom_render_to_response
from django.utils import simplejson
from djangotoolbox.http import JSONResponse
from ordering.models import OrderType, StationFixedPriceRule

def info(request):
    return custom_render_to_response("wb_info.html", locals(), context_instance=RequestContext(request))

def the_service(request):
    page_name = page_specific_class = "the_service"
    return custom_render_to_response("the_service.html", locals(), context_instance=RequestContext(request))

def about_us(request):
    return custom_render_to_response("about_faq_contact.html", locals(), context_instance=RequestContext(request))

def contact(request):
    page_name = page_specific_class = "contact"
    return custom_render_to_response("contact.html", locals(), context_instance=RequestContext(request))

@force_lang("he") # for now show this page only in hebrew
def privacy(request):
    page_name = page_specific_class = "privacy"
    return custom_render_to_response("privacy.html", locals(), context_instance=RequestContext(request))

@force_lang("he") # for now show this page only in hebrew
def terms(request):
    page_name = page_specific_class = "terms"
    return custom_render_to_response("terms_of_service.html", locals(), context_instance=RequestContext(request))

def faq(request):
    page_name = page_specific_class = "faq"
    return custom_render_to_response("faq.html", locals(), context_instance=RequestContext(request))

def my_rides(request):
    page_name = page_specific_class = "my_rides"
    order_types = simplejson.dumps({'private': OrderType.PRIVATE,
                                    'shared': OrderType.SHARED})

    return custom_render_to_response("my_rides.html", locals(), context_instance=RequestContext(request))

def get_sharing_cities(request):
    cities = get_sharing_cities_data()
    return JSONResponse(cities)

def get_sharing_cities_data():
    default_city_name = u"תל אביב יפו"
    city_names = [u"גבעתיים", u"רמת גן", default_city_name]
    cities = sorted(City.objects.filter(name__in=city_names), key=lambda city: city.name)

    # put the default city first
    idx = None
    for i, city in enumerate(cities):
        if city.name == default_city_name:
            idx = i
            break

    if idx:
        default_city = cities.pop(idx)
        cities.insert(0, default_city)

    return [{'id': city.id, 'name': city.name} for city in cities]

def welcome_email(request):
    return render_to_response("welcome_email.html")