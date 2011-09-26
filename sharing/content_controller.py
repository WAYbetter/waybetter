from django.template.context import RequestContext
from common.util import custom_render_to_response

def info(request):
    return custom_render_to_response("wb_info.html", locals(), context_instance=RequestContext(request))

def privacy(request):
    page_specific_class = "privacy_he"
    return custom_render_to_response("privacy_he.html", locals(), context_instance=RequestContext(request))

def terms(request):
    page_specific_class = "terms_he"
    return custom_render_to_response("terms_he.html", locals(), context_instance=RequestContext(request))

  