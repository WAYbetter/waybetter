#import os
#os.environ["DJANGO_SETTINGS_MODULE"] = "settings"

def setup():

    # setup appengine task queue
    import os
    from google.appengine.api import apiproxy_stub_map
    taskqueue_stub = apiproxy_stub_map.apiproxy.GetStub('taskqueue')
    taskqueue_stub._root_path = os.path.join(os.path.dirname(__file__), '..')


## fix datastore path
#from django.conf import settings
#
#_ds_pathinfo = {
#            'datastore_path': '/home/amir/dev/data/waybetter.datastore',
#            'history_path': "/home/amir/dev/data/waybetter.datastore.history',
#        }
#
#settings.DATABASES['gae'].update(_ds_pathinfo)