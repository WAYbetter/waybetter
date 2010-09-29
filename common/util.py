import random

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