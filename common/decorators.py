from django.http import HttpResponseForbidden, HttpResponse
from django.db import models

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

def order_in_relation_to_field(clas, field_name):
    if not getattr(clas, field_name):
        raise AttributeError("field_name '%s' must be a field name on class '%s'" % (field_name, clas))

    order_field_name = "_%s_order" % field_name
    clas_field_name = clas._meta.verbose_name.replace(" ", "_")
    set_order_func_name = "set_%s_order" % field_name

    clas._meta.abstract = True

    def _set_order(self, new_order):
        field_id = getattr(self, field_name).id
        setattr(self, order_field_name, "%d__%s" % (field_id, '1' * (new_order + 1)))

    @classmethod
    def _sort_ids_by_order(cls, array_of_ids):
        """
        Sort an array of ids according to the order defined

        @param cls:
        @param array_of_ids: array of this model ids
        @return: sorted array of ids
        """
        array_of_ids = [int(v) for v in array_of_ids] # convert to int
        sorted_ids = [ca.id for ca in cls.objects.filter(id__in=array_of_ids)] # get ids sorted by ordering
        return sorted_ids

    @classmethod
    def _sort_models(cls, list_of_models, rel_field_name=clas_field_name):
        """
        Sort the given models by the defined order

        @param cls:
        @param list_of_models:
        @param rel_field_name: if the field name on the model is not "city_area"
        @return: the sorted list
        """
        return sorted(list_of_models, key = lambda element: getattr(getattr(element, rel_field_name), field_name))

    class wrapper_class(clas):
        def save(self, **kwargs):
            if not getattr(self, order_field_name):
                count = self.__class__.objects.filter(city=getattr(self, field_name)).count()
                getattr(self, set_order_func_name)(count)

            super(wrapper_class, self).save(**kwargs)

    wrapper_class._meta = clas._meta
    wrapper_class._meta.abstract = False
    wrapper_class._meta.ordering = [order_field_name]
    models.CharField(null=True, blank=True).contribute_to_class(wrapper_class, order_field_name)
    setattr(wrapper_class, set_order_func_name,  _set_order)
    setattr(wrapper_class, "sort_ids_by_%s_order" % field_name,  _sort_ids_by_order)
    setattr(wrapper_class, "sort_models_by_%s_order" % field_name,  _sort_models)
    return wrapper_class
