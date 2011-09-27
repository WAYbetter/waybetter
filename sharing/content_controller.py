from django.template.context import RequestContext
from common.util import custom_render_to_response

def info(request):
    return custom_render_to_response("wb_info.html", locals(), context_instance=RequestContext(request))

def about(request):
    page_name = page_specific_class = "about"
    return custom_render_to_response("wb_about.html", locals(), context_instance=RequestContext(request))

def contact(request):
    page_name = page_specific_class = "contact"
    return custom_render_to_response("contact.html", locals(), context_instance=RequestContext(request))

def privacy(request):
    page_name = page_specific_class = "privacy"
    return custom_render_to_response("privacy_he.html", locals(), context_instance=RequestContext(request))

def terms(request):
    page_name = page_specific_class = "terms"
    return custom_render_to_response("terms_he.html", locals(), context_instance=RequestContext(request))

  