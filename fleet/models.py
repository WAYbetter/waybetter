from common.models import BaseModel
from django.db import models
from django.utils.importlib import import_module

class FleetManager(BaseModel):
    name = models.CharField(max_length=50)
    backend_path = models.CharField(max_length=50, default="fleet.backends.default.DefaultFleetManager")

    def __init__(self, *args, **kwargs):
        super(FleetManager, self).__init__(*args, **kwargs)

        i = self.backend_path.rfind('.')
        module, attr = self.backend_path[:i], self.backend_path[i+1:]

        mod = import_module(module)
        self.backend = getattr(mod, attr)

    def __unicode__(self):
        return self.name