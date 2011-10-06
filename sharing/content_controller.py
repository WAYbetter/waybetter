from django.template.context import RequestContext
from common.util import custom_render_to_response
from django.utils import simplejson
from ordering.models import OrderType

def info(request):
    return custom_render_to_response("wb_info.html", locals(), context_instance=RequestContext(request))

def the_service(request):
    page_name = page_specific_class = "the_service"
    return custom_render_to_response("the_service.html", locals(), context_instance=RequestContext(request))

def about_us(request):
    page_name = page_specific_class = "about_us"
    return custom_render_to_response("about_us.html", locals(), context_instance=RequestContext(request))

def contact(request):
    page_name = page_specific_class = "contact"
    return custom_render_to_response("contact.html", locals(), context_instance=RequestContext(request))

def privacy(request):
    page_name = page_specific_class = "privacy"
    return custom_render_to_response("privacy_he.html", locals(), context_instance=RequestContext(request))

def terms(request):
    page_name = page_specific_class = "terms"
    return custom_render_to_response("terms_he.html", locals(), context_instance=RequestContext(request))

def faq(request):
    page_name = page_specific_class = "faq"
    return custom_render_to_response("faq.html", locals(), context_instance=RequestContext(request))

def my_rides(request):
    page_name = page_specific_class = "my_rides"
    order_types = simplejson.dumps({'private': OrderType.PRIVATE,
                                    'shared': OrderType.SHARED})

    return custom_render_to_response("my_rides.html", locals(), context_instance=RequestContext(request))
