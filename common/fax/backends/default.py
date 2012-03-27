import logging
from common.util import Enum

class FaxStatus(Enum):
    DONE    	= 0
    PENDING		= 1
    QUEUED      = 2
    IN_PROGRESS = 3
    ERROR       = 4

class AbstractFaxBackend(object):
    def __init__(self):
        logging.info("Registering <%s> as Fax Backend" % self.__class__.__name__)

    @staticmethod
    def send_fax(fax_number, html, title):
        """
        Sends the given html document to the specified destination

        @param fax_number: fax number or printer id
        @param html: html file to send
        @param title: title of the fax
        @return: a job id that cab be then passed to C{get_status} to retrieve the status of the job
        """
        raise NotImplementedError("send_fax is not implemented")

    @staticmethod
    def get_status(id):
        """
        Queries the backend service for the status of the given id

        @param id: a job id. id is the result of the C{send_fax} method
        @return: a C{FaxStatus} value
        """
        raise NotImplementedError("get_status is not implemented")

class NoopFaxBackend(AbstractFaxBackend):
    @staticmethod
    def send_fax(fax_number, html, title):
        logging.info("Skipping sending fax to: %s" % fax_number)
        return True

    @staticmethod
    def get_status(fax_id):
        logging.info("Skipping checking status for: %s" % fax_id)
        return FaxStatus.DONE
