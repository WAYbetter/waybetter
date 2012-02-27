from common.fax.backends.freefax import FreefaxBackend

DEFAULT_BACKEND = FreefaxBackend()

class Faxer(object):
    def __init__(self, backend=None):
        self.backend = backend or DEFAULT_BACKEND
    def send_fax(self, fax_number, html, title=None):
        return self.backend.send_fax(fax_number, html, title)

    def get_status(self, fax_id):
        return self.backend.get_status(fax_id)