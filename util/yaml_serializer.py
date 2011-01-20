# run from ./manage shell

# for unicode see: http://docs.python.org/howto/unicode.html#reading-and-writing-unicode-data

from django.db import models
from django.core import serializers

# non-app models should be imported
from django.contrib.auth.models import User

OUTPUT_FILE = "/home/amir/dev/data/serialized_data.yaml"
APPS_TO_DUMP = {"ordering": ("Station", "WorkStation"),
                #"common": ("City", "Country")
}

out = open(OUTPUT_FILE, 'w')

for app in APPS_TO_DUMP.keys():
    for model in APPS_TO_DUMP[app]:
        modelclass = models.get_model(app, model)
        if modelclass:
            data = serializers.serialize("yaml", modelclass.objects.all())
            out.write(data)
        else:
            raise ImportError("error serializing model %s.%s" % (app,model))

# non-app models should be serialized separately :-(
data = serializers.serialize("yaml", User.objects.all())
out.write(data)

out.close()



