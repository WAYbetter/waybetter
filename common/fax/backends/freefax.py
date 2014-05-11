import logging
from common.fax.backends.default import AbstractFaxBackend, FaxStatus
from common.suds_appengine import GAEClient
import base64

SEND_FAX_URL = "http://www.freefax.co.il/ws/ws2.wsdl"
FAX_STATUS_URL = "http://www.freefax.co.il/ws/gs2.wsdl"
USERNAME = "***REMOVED***"
PASSWORD = "***REMOVED***"

class FreefaxBackend(AbstractFaxBackend):
    @staticmethod
    def send_fax(fax_number, html, title):
        client = GAEClient(SEND_FAX_URL)
        html = html.encode("utf-8", 'ignore')
        params = [USERNAME, PASSWORD, "send", str(fax_number), "now", "dontemailperfax", "noreply@waybetter.com", title,
                  base64.b64encode(html)]
        try:
            res = client.service.SendFax(",".join(params))
        except Exception, e:
            res = None
            logging.error("Freefax send_fax failed: %s" % e.message)

        return res

    @staticmethod
    def get_status(fax_id):
        client = GAEClient(FAX_STATUS_URL)
        params = [USERNAME, PASSWORD, fax_id]
        try:
            res = client.service.GetStatus(",".join(params))
            logging.info("res = %s" % res)
        except Exception, e:
            res = None
            logging.error("Freefax get status failed: %s" % e.message)

        if res and not res.startswith("ERROR"):
            d = {}
            vals = [r.strip() for r in res.split(",")]
            for v in vals:
                k, v = v.split("=")[:2]
                d[k] = v

            if d.get("stat") == "done":
                res = FaxStatus.DONE
            else:
                res = FaxStatus.QUEUED
        else:
            res = FaxStatus.ERROR

        return res