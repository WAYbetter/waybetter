import logging

class AbstractFaxBackend(object):
    @staticmethod
    def send_fax(fax_number, html, title):
        raise NotImplementedError("send_fax is not implemented")

    @staticmethod
    def get_status(fax_id):
        raise NotImplementedError("get_status is not implemented")

class NoopFaxBackend(AbstractFaxBackend):
    @staticmethod
    def send_fax(fax_number, html, title):
        logging.info("Sent fax to: %s" % fax_number)

    @staticmethod
    def get_status(fax_id):
        logging.info("Status checked for: %s" % fax_id)
