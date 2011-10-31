from django.conf.urls.defaults import *
from django.conf import settings
from django.views.generic.simple import direct_to_template


urlpatterns = patterns('',
    (r'setup/$', 'common.views.setup'),
    (r'reset_ws_passwords/$', 'common.views.reset_password'),
    (r'test_channel/$', 'common.views.test_channel'),
    (r' /$', 'common.views.init_countries'),
    (r'is_email_available/$', 'common.services.is_email_available'),
    (r'is_email_available_for_user/$', 'common.services.is_email_available_for_user'),
    (r'is_username_available/$', 'common.services.is_username_available'),
    (r'get_polygons/$', 'common.services.get_polygons'),
    (r'update_city_area_order/$', 'common.services.update_city_area_order'),
    (r'init_(?P<model_name>\w+)_order/$', 'common.services.init_model_order'),
    (r'run_task/$', 'common.maintenance.run_maintenance_task'),
    (r'run_task_on_queue/$', 'common.maintenance.maintenance_task'),
    (r'maintenance/routing_service_test$', 'common.maintenance.run_routing_service_test'),
    (r'maintenance/routing_service_test_task$', 'common.maintenance.test_routing_service_task'),
    (r'registration/get_login_form/$', 'common.registration.get_login_form'),
    (r'registration/get_error_form/$', 'common.registration.get_error_form'),
    (r'registration/get_registration_form/$', 'common.registration.get_registration_form'),
    (r'registration/get_credentials_form/$', 'common.registration.get_credentials_form'),
    (r'registration/get_phone_verification_form/$', 'common.registration.get_phone_form'),
    (r'registration/get_cant_login_form/$', 'common.registration.get_cant_login_form'),
    (r'registration/get_phone_code_form/$', 'common.registration.get_phone_code_form'),
    (r'registration/get_sending_form/$', 'common.registration.get_sending_form'),
    (r'error/$', 'common.views.error_page'),
    (r'error_dialog/$', 'common.views.error_dialog'),
    (r'feedback/$', 'common.registration.feedback'),
    (r'broadcast_signal/$', 'common.signals.send_async'),
    (r'flush_memcache/$', 'common.geocode.flush_memcache'),
    url(r'get_terms/$', direct_to_template, {'template': "terms_form.html"} ,name="terms_dialog"),
    url(r'map_provider_loader\.js/$', direct_to_template, { 'template': "map_provider_loader.js", 
                                                            'extra_context': { "map_provider_url": settings.MAP_PROVIDER_LIB_URL },
                                                            'mimetype': 'text/javascript' }),

)

 