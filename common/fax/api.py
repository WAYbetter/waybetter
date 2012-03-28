import logging
from django.conf import settings
from common.fax.backends.default import NoopFaxBackend
from common.fax.backends.google_cloud_print import GoogleCloudPrintBackend

if settings.DEV:
    DEFAULT_BACKEND = NoopFaxBackend()
else:
    DEFAULT_BACKEND = GoogleCloudPrintBackend()

def send_fax(destination, html, title=None, backend=None):
    """
    Sends the given html document to the given destination

    @param destination: either a fax_number or a printer_id, depending on the default backend
    @param html: the document to be sent
    @param title: a title for the document
    @param backend: a backend instance to use for this call
    @return: a job id that can be used with C{get_status}
    """
    if not backend:
        backend = DEFAULT_BACKEND

    return backend.send_fax(destination, html, title)

def get_status(id, backend=None):
    """
    Return the status of the given id

    @param id: returned from C{send_fax}
    @param backend: a backend instance to use for this call
    @return: a C{FaxStatus} value
    """

    if not backend:
        backend = DEFAULT_BACKEND

    return backend.get_status(id)