from django.conf.urls.defaults import *
from django.views.generic.simple import direct_to_template


urlpatterns = patterns('',
    (r'create_selenium_test_data/$', 'testing.test_data.create_selenium_test_data'),
    (r'destroy_selenium_test_data/$', 'testing.test_data.destroy_selenium_test_data'),
)

 