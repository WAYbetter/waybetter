from django.conf import settings

def dev(request):
    return {'DEV': settings.DEV}
  