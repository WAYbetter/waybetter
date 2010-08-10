from google.appengine.api import xmpp
from django.utils import simplejson
from django.conf import settings
from ordering.errors import OrderError

def is_workstation_available(work_station):
    user_name = work_station.im_user
    if user_name:
        return xmpp.get_presence(user_name)

    return False

def push_order(order_assignment):
    user_name = order_assignment.work_station.im_user

    return_status = xmpp.send_message(user_name, simplejson.dumps(order_assignment), settings.SYSTEM_IM_USER, xmpp.MESSAGE_TYPE_CHAT)
    if return_status[0] != xmpp.NO_ERROR:
        raise OrderError("An error occurred while sending order to station: %s" % xmpp.XmppMessageResponse.XmppMessageStatus_Name(return_status[0]))

    