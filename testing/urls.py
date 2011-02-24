from django.conf.urls.defaults import *
from django.views.generic.simple import direct_to_template


urlpatterns = patterns('',
    (r'create_selenium_test_data/$', 'testing.setup_testing_env.create_selenium_test_data'),
    (r'destroy_selenium_test_data/$', 'testing.setup_testing_env.destroy_selenium_test_data'),
)

 