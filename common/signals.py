from common.decorators import internal_task_on_queue, catch_view_exceptions
from common.models import BaseModel
from django.core.urlresolvers import reverse
from django.db import models
from django.dispatch.dispatcher import Signal, _make_id
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from google.appengine.api import taskqueue
import logging
import pickle
from common.util import Enum

class SignalStore(BaseModel):
    '''
    A simple model to hold signal data until processed
    '''
    pickled_value = models.TextField("pickled value")

    def get_signal_data(self):
        data = pickle.loads(self.pickled_value.encode("utf-8"))
        if "obj_id" in data:
            obj_id = data.pop("obj_id")
            obj_type = data.pop("obj_type")
            obj = obj_type.objects.get(id=obj_id)
            data["obj"] = obj

        return data

    def set_signal_data(self, data):
        if "obj" in data:
            o = data.pop("obj")
            data["obj_id"] = o.id
            data["obj_type"] = type(o)
            
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
    """
    A sub-class of TypedSignal that sends the signal asynchronously
    to registered receivers
    """
    def send(self, sender, **named):
        """
        Send this signal asynchronously to the registered receivers

        @param sender: sender 
        @param named: named arguments
        @return:
        """
        if not self.receivers:
            logging.warning("no receivers found. sender: %s, signal type: %s" % (sender, self.signal_type))
            return None

        logging.info("sending signal: %s" % self.signal_type)

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
@catch_view_exceptions
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
class AsyncComputationSignalType(Enum):
    SUBMITTED                   = 1
    COMPLETED                   = 2
    FAILED                      = 3

async_computation_submitted_signal = AsyncSignal(AsyncComputationSignalType.SUBMITTED, providing_args=["channel_id"])
async_computation_completed_signal = AsyncSignal(AsyncComputationSignalType.COMPLETED, providing_args=["channel_id", "data", "token"])
async_computation_failed_signal = AsyncSignal(AsyncComputationSignalType.FAILED, providing_args=["channel_id"])
