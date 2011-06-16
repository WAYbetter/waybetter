from django.http import HttpResponseForbidden, HttpResponse
from google.appengine.ext import db
from common.util import notify_by_email
import logging
import traceback

def catch_view_exceptions(function=None):
    def wrapper(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except Exception, e:
            trace = traceback.format_exc()
            logging.error("Exception caught by decorator:\n %s" % trace)
            notify_by_email("Exception caught by decorator", trace)
            return HttpResponse("Exception caught by decorator")

    return wrapper

def internal_task_on_queue(queue_name):
    """
    Ensures request has the matching HTTP_X_APPENGINE_QUEUENAME header
    """
    def actual_decorator(function):

        def wrapper(request):
            if hasattr(request, '_dont_enforce_csrf_checks' ) and request._dont_enforce_csrf_checks:
                return function(request)

            if request.META.get('HTTP_X_APPENGINE_QUEUENAME', "") != queue_name:
                return HttpResponseForbidden("Invalid call to internal task")

            return function(request)

        return wrapper

    return actual_decorator

def run_in_transaction(function=None):
    """
    Decorator for running transactions
    """
    def wrapper(*args, **kwargs):
        return db.run_in_transaction(function, *args, **kwargs)

    return wrapper

def receive_signal(*signals, **kwargs):
    '''
    Register the given function as a signal handler for the given signals
    '''
    def actual_decorator(function):
        for signal in signals:
            signal.connect(function, weak=False, **kwargs)
        return function

    return actual_decorator

def allow_JSONP(function):
    """
    support JSONP if request has callback=? parameter
    """
    def wrapper(request):
        callback = request.GET.get("callback")
        if callback:
            try:
                response = function(request)
            except:
                response = HttpResponse('error', status=500)

            if response.status_code / 100 != 2:
                response.content = 'error'

            if response.content[0] not in ['"', '[', '{'] or response.content[-1] not in ['"', ']', '}']:
                response.content = '"%s"' % response.content
                
            response.content = "%s(%s)" % (callback, response.content) 
            response['Content-Type'] = 'application/javascript'
        else:
            response = function(request)

        return response
    return wrapper
