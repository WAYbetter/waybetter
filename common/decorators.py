from django.http import HttpResponseForbidden
from google.appengine.ext import db

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
    def wrapper(*args):
        return db.run_in_transaction(function, *args)

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