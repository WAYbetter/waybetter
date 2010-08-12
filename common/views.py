# Create your views here.
from django.contrib.auth.models import User
from django.http import HttpResponse
from ordering.models import Order, WorkStation
from google.appengine.api import xmpp


def setup(request):
    if "token" in request.GET:
        if request.GET["token"] == 'waybetter_init':
            if User.objects.filter(username = "waybetter_admin").count() == 0:
                u = User()
                u.username = "waybetter_admin"
                u.set_password('waybetter_admin')
                u.email = "guykrem@gmail.com"
                u.is_active = True
                u.is_staff = True
                u.is_superuser = True
                u.save()
                return HttpResponse('Admin created!')

        if request.GET["token"] == 'send_invites':
            count = 0
            for ws in WorkStation.objects.all():
                count = count + 1
                xmpp.send_invite(ws.im_user)

            return HttpResponse('Sent invites to %d work station' % count)



    return HttpResponse('Wrong usage! (pass token)')
