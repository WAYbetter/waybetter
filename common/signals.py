import traceback
from google.appengine.ext import deferred
from common.decorators import   receive_signal
from common.util import Enum, get_uuid
from django.dispatch.dispatcher import Signal, _make_id
from django.http import HttpResponse
from django.utils import simplejson
from google.appengine.api.channel.channel import InvalidChannelClientIdError
from google.appengine.api import  memcache, channel
import logging
import pickle


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
    @staticmethod
    def dump_signal_data(data):
        if "obj" in data:
            o = data.pop("obj")
            data["obj_id"] = o.id
            data["obj_type"] = type(o)

        try:
            return pickle.dumps(data)
        except pickle.PicklingError, e:
            trace = traceback.format_exc()
            logging.error("PicklingError caught:\n %s" % trace)
            raise

    @staticmethod
    def load_signal_data(pickled_data):
        data = pickle.loads(pickled_data.encode("utf-8"))
        if "obj_id" in data:
            obj_id = data.pop("obj_id")
            obj_type = data.pop("obj_type")
            obj = obj_type.objects.get(id=obj_id)
            data["obj"] = obj

        return data

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
            args = {"receiver": receiver, "sender": sender, "signal_type": self.signal_type}
            args.update(named)

            signal_data = AsyncSignal.dump_signal_data(args)

            deferred.defer(send_async, signal_data=signal_data, _queue="signals", _name="send-signal-%s-%s-%s" % (sender, self.signal_type, get_uuid()))

        return None # discard the responses


def send_async(signal_data):
    try:
        d = AsyncSignal.load_signal_data(signal_data)
        logging.info("broadcasting signal sender=%s signal_type=%s" % (d.get("sender"), d.get("signal_type")))

        receiver = d.pop("receiver")
        receiver(**d)

    except Exception, e: # prevent this signal from being re-dispatched in case of error
        trace = traceback.format_exc()
        logging.error("Error dispatching signal: %s: %s: %s\n%s" % (id, type(e).__name__, e.message, trace))

    return HttpResponse("OK")


class AsyncComputationSignalType(Enum):
    SUBMITTED                   = 1
    COMPLETED                   = 2
    FAILED                      = 3

async_computation_submitted_signal = AsyncSignal(AsyncComputationSignalType.SUBMITTED, providing_args=["channel_id"])
async_computation_completed_signal = AsyncSignal(AsyncComputationSignalType.COMPLETED, providing_args=["channel_id", "data", "token"])
async_computation_failed_signal = AsyncSignal(AsyncComputationSignalType.FAILED, providing_args=["channel_id"])

@receive_signal(async_computation_completed_signal)
def async_computation_complete_handler(sender, signal_type, **kwargs):
    from common.views import ASYNC_MEMCACHE_KEY
    client_id = kwargs.get('channel_id')
    token = kwargs.get('token')
    logging.info("async_computation_complete_handler: channel_id: %s, data: %s" % (client_id, kwargs.get('data')))
    json = simplejson.dumps(kwargs.get('data'))

    # save data to memcache
    memcache.set(ASYNC_MEMCACHE_KEY % token, json)

    try:
        channel.send_message(client_id, json)
    except InvalidChannelClientIdError:
        logging.error("InvalidChannelClientIdError: could not sent message '%s' with channel id: '%s'" % (json,client_id))
