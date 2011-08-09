from django.db.models.fields.related import ForeignKey
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
    """
    Makes clas ordered relative to field_name

    Adds the following instance methods:

        - C{set_<field_name>_order}

    Add the following class methods:

        - C{sort_ids_by_<field_name>_order}

        - C{sort_models_by_<field_name>_order}

        - C{init_<field_name>_order}


    @param clas: a model Class
    @param field_name: a ForeignKey field on the class
    @return: 
    """

    # check that given field_name is a ForeignKey
    if not isinstance(clas._meta.get_field_by_name(field_name)[0], ForeignKey):
        raise AttributeError("field_name '%s' must be a ForeignKey on given class" % field_name)

    order_field_name = "_%s_order" % field_name
    clas_field_name = clas._meta.verbose_name.replace(" ", "_")
    set_order_func_name = "set_%s_order" % field_name

    def _set_order(self, new_order):
        """
        Sets the order of the instance
        
        @param new_order: the new order index
        @return:
        """
#        logging.info("%s is setting new order: %d" % (self, new_order))
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

    @classmethod
    def _init_order(cls):
        related_field_manager = getattr(cls, field_name).field.rel.to
        for related in related_field_manager.objects.all():
#            logging.info("related: %s" % related)
            for i, m in enumerate(cls.objects.filter(**{field_name: related}).order_by()):
#                logging.info("i, m: %s, %s" %  (i,m))
                getattr(m, set_order_func_name)(i)
                m.save()

    def _save(self, **kwargs):
        if not getattr(self, order_field_name):
            count = self.__class__.objects.filter(field_name=getattr(self, field_name)).count()
            getattr(self, set_order_func_name)(count)

        super(clas, self).save(**kwargs)

    # add ordering field to class
    models.CharField(null=True, blank=True).contribute_to_class(clas, order_field_name)

    # set ordering by field
    clas._meta.ordering = [order_field_name]

    # patch class
    setattr(clas, "save",  _save)
    setattr(clas, set_order_func_name,  _set_order)
    setattr(clas, "sort_ids_by_%s_order" % field_name,  _sort_ids_by_order)
    setattr(clas, "sort_models_by_%s_order" % field_name,  _sort_models)
    setattr(clas, "init_%s_order" % field_name,  _init_order)

    return clas
