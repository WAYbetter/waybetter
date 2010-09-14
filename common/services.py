import time

from django.http import HttpResponse
from django.contrib.auth.models import User


def is_username_available(request):
    #TODO_WB:throttle this
    result = False
    username = request.GET.get("username")
    if (username):
        time.sleep(1)
        result = User.objects.filter(username=username).count() == 0

    if result:
        return HttpResponse("true")
    else:
        return HttpResponse("false")