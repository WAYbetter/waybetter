from django.http import HttpResponse
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from djangotoolbox.http import JSONResponse
from suds.client import Client
from backends import isr as isr_backend
import inspect
import logging

def authenticate(request):
    logging.getLogger('suds').setLevel(logging.ERROR)

    url = "http://81.218.41.97/xmlp_service/Taxi_Orders.asmx?wsdl"
    client = Client(url)
    logging.info(client)

    auth_number = client.service.Authenticate("waybetter", "l3mMbXbWNy7cHfHNHCG1SOpEI62b58Tv")
    logging.info(auth_number)
    return HttpResponse(auth_number)


def isr_view(request):
    if request.method == "POST":
        result = ""
        method_name = request.POST.get("method_name")
        try:
            method = getattr(isr_backend, method_name)
            args = inspect.getargspec(method)[0]
            values = [request.POST.get(arg) for arg in args]
            result = method(*values)

        except Exception, e:
            result = e.message

        return JSONResponse({'result': result})
    else:
        methods = []
        method_type = type(lambda x: x)
        for attr_name in dir(isr_backend):
            if attr_name.startswith("_"):
                continue
            attr = getattr(isr_backend, attr_name)
            if type(attr) == method_type:
                args = inspect.getargspec(attr)[0]
                methods.append({'name': attr.func_name, 'args': args, 'doc': attr.func_doc or ""})

        return render_to_response("isr_view.html", locals(), RequestContext(request))