# import this file to setup the django/appengine environment in files that might init a new instance of the app

from djangoappengine import main

from django.utils.importlib import import_module
from django.conf import settings

# load all models.py to ensure signal handling installation or index loading
# of some apps
for app in settings.INSTALLED_APPS:
    try:
        import_module('%s.models' % app)
    except ImportError:
        pass
