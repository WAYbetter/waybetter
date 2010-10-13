import random
from django.http import HttpResponse
from django.utils import simplejson

def is_empty(str):
    """
    return True pf string is emtpy, spaces only or None
    """
    return not str or len(str.strip()) == 0


# python weekdays (see: datetime.weekday()): monday=0 .. sunday=6
PYTHON_WEEKDAY_MAP = {
    6: 1,
    0: 2,
    1: 3,
    2: 4,
    3: 5,
    4: 6,
    5: 7
}

def convert_python_weekday(wd):
    return PYTHON_WEEKDAY_MAP[wd]

def gen_verification_code():
    return random.randrange(1000,10000)

def get_model_from_request(model_class, request):
        if (not request.user or not request.user.is_authenticated()):
            return None
        try:
            model_instance = model_class.objects.filter(user = request.user).get()
        except model_class.DoesNotExist:
            return None

        return model_instance
