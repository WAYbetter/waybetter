from fleet.models import AbstractFleetManager

class DefaultFleetManager(AbstractFleetManager):
    @classmethod
    def create_order(cls, order, station_id):
        return None

    @classmethod
    def cancel_order(cls, order_id):
        return False

    @classmethod
    def get_order(cls, order_id):
        return None

