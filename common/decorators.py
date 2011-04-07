from google.appengine.ext import db

def run_in_transaction(function=None):
    """
    Decorator for running transactions
    """
    def wrapper(*args):
        return db.run_in_transaction(function, *args)

    return wrapper
  