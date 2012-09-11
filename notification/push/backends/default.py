import logging

class AbstractPushBackend(object):
    def __init__(self):
        logging.info("Registering <%s> as Push Backend" % self.__class__.__name__)

    def push(self, pushID, payload, extra=None):
        raise NotImplementedError("push is not implemented")
