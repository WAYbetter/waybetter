class AbstractFleetManager(object):
    @classmethod
    def create_order(cls, order):
        raise NotImplementedError()

    @classmethod
    def cancel_order(cls, order):
        raise NotImplementedError()

    @classmethod
    def get_order_status(cls, order):
        raise NotImplementedError()


class DefaultFleetManager(AbstractFleetManager):
    pass


