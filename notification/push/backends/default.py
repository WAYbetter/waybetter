import logging

class AbstractPushBackend(object):
    def __init__(self):
        logging.info("Registering <%s> as Push Backend" % self.__class__.__name__)

    def push(self, pushID, platform, payload, extra=None):
        raise NotImplementedError("push is not implemented")

    def deregister(self, pushID, platform):
        raise NotImplementedError("deregister is not implemented")

    def is_active(self, pushID, platform):
        raise NotImplementedError("is_active is not implemented")