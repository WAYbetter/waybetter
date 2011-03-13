import time
from django.contrib.auth.models import User
from django.http import HttpResponse

def is_email_available(request):
    #TODO_WB:throttle this
    result = False
    email = request.GET.get("email")
    if email:
        time.sleep(1)
        result = User.objects.filter(email=email).count() == 0

    if result:
        return HttpResponse("true")
    else:
        return HttpResponse("false")