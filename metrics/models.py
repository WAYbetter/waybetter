from django.db import models
from common.models import BaseModel

# Create your models here.
class ModelMetric(BaseModel):
    
    class Meta:
        abstract = True

    name = models.CharField(max_length=30)
    weight = models.FloatField()
    function_name = models.CharField(max_length=50) # name of the function to compute: e.g., 'ordering.station_rating.distance'

    def __unicode__(self):
        return self.name

    def compute(self, *args, **kwargs):
        split = self.function_name.split(".")

        m = __import__(".".join(split[:-1]), fromlist=[split[-1]])
        f = getattr(m, split[-1])
        return f(*args, **kwargs)


class StationMetric(ModelMetric):
    pass

class WorkStationMetric(ModelMetric):
    pass
