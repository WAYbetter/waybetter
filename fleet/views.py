import traceback
import inspect
from django.http import HttpResponse
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from django.utils import simplejson
from djangotoolbox.http import JSONResponse
from fleet import fleet_manager

def get_ride_status(request, ride_id):
    fleet_manager.query_backends()
    result = fleet_manager.get_fmr(ride_id)
    if request.is_ajax():
        return JSONResponse({'result': str(result)})
    else:
        return HttpResponse(result)


def isr_testpage(request):
    from fleet import isr_tests

    if request.method == "POST":
        result = ""
        method_name = request.POST.get("method_name")
        try:
            method = getattr(isr_tests, method_name)
            args = inspect.getargspec(method)[0]
            values = [request.POST.get(arg) for arg in args]
            result = method(*values)

        except Exception, e:
            trace = traceback.format_exc()
            result = trace

        try:
            result = simplejson.dumps(result)
        except TypeError: # not json serializable
            result = str(result)

        return JSONResponse({'result': result})
    else:
        methods = []
        method_type = type(lambda x: x)
        for attr_name in dir(isr_tests):
            if attr_name.startswith("_"):
                continue
            attr = getattr(isr_tests, attr_name)
            if type(attr) == method_type:
                args = inspect.getargspec(attr)[0]
                methods.append({'name': attr.func_name, 'args': args, 'doc': attr.func_doc or ""})

        return render_to_response("isr_testpage.html", locals(), RequestContext(request))