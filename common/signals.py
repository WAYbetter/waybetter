from common.decorators import internal_task_on_queue
from common.util import BaseModel
from django.core.urlresolvers import reverse
from django.db import models
from django.dispatch.dispatcher import Signal, _make_id
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from google.appengine.api import taskqueue
import logging
import pickle

class SignalStore(BaseModel):
    '''
    A simple model to hold signal data until processed
    '''
    pickled_value = models.TextField("pickled value")

    create_date = models.DateTimeField("create date", auto_now_add=True)
    modify_date = models.DateTimeField("modify date", auto_now=True)

    def get_signal_data(self):
        return pickle.loads(self.pickled_value.encode("utf-8"))

    def set_signal_data(self, data):
        self.pickled_value = pickle.dumps(data)

#    define signal_data property
    signal_data = property(get_signal_data, set_signal_data)

class TypedSignal(Signal):
    '''
    A sub-class of django.dispatch.dispatcher.Signal that keeps a list of all signals (.all)
    Adds signal_type argument to all signals
    '''
    all = set() # maintain a list of all signals

    def __init__(self, signal_type, providing_args=None):
        self.signal_type = signal_type

        if not providing_args:
            providing_args = []

        super(TypedSignal, self).__init__(providing_args.append("signal_type"))
        TypedSignal.all.add(self)

class AsyncSignal(TypedSignal):
    '''
    A sub-class of TypedSignal that sends the signal asynchronously
    to registered receivers
    '''
    def send(self, sender, **named):
        '''
        Send this signal asynchronously to the registered receivers
        '''
        if not self.receivers:
            return None

        for receiver in self._live_receivers(_make_id(sender)):
            args = {"receiver": receiver, "signal": self, "sender": sender, "signal_type": self.signal_type}
            args.update(named)

            # store the signal to the signal store
            stored_signal = SignalStore(signal_data=args)
            stored_signal.save()

            t = taskqueue.Task(url=reverse(send_async), params={"id": stored_signal.id}, name="send-signal-%s" % stored_signal.id)
            q = taskqueue.Queue('signals')
            q.add(t)

        return None # discard the responses

@csrf_exempt
@internal_task_on_queue("signals")
def send_async(request):
    id = request.POST.get("id")
    try:
        stored_signal = SignalStore.by_id(id)
        d = stored_signal.signal_data

        receiver = d.pop("receiver")
        receiver(**d)

        stored_signal.delete() # delete the signal unless there was an exception
    except Exception, e: # prevent this signal from being re-dispatched in case of error
        logging.error("Error dispatching signal: %s: %s: %s" % (id, type(e).__name__, e.message))

    return HttpResponse("OK")
