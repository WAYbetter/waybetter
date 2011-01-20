# run from ./manage shell

# for unicode see: http://docs.python.org/howto/unicode.html#reading-and-writing-unicode-data

from django.db import models
from django.core import serializers

# non-app models to dump
from django.contrib.auth.models import User

APPS_TO_DUMP = {"ordering": ("Passenger", "Station", "WorkStation"),
                #"common": ("City",)
}

file_name = ""

for app in APPS_TO_DUMP.keys():
    file_name += app.upper() + "."
    for model in APPS_TO_DUMP[app]:
        file_name += model.lower() + ","

output_file = "/home/amir/dev/data/" + file_name + ".json"

out = open(output_file, 'w')

for app in APPS_TO_DUMP.keys():
    for model in APPS_TO_DUMP[app]:
        modelclass = models.get_model(app, model)
        if modelclass:
            serializers.serialize("json", modelclass.objects.all(), indent=2, stream=out)
        else:
            print "error in models %s.%s" % (app,model)


# non-app models should be serialized separately :-(
serializers.serialize("json", User.objects.all(), indent=2, stream=out)

out.close()




