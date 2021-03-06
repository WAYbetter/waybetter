from django.conf.urls.defaults import *
from django.conf import settings
from django.views.generic.simple import direct_to_template


urlpatterns = patterns('',
    (r'setup/$', 'common.views.setup'),
    (r'reset_ws_passwords/$', 'common.views.reset_password'),
    (r'test_channel/$', 'common.views.test_channel'),
    (r'test_ga/$', 'common.views.test_ga'),
    (r' /$', 'common.views.init_countries'),
    (r'is_email_available/$', 'common.services.is_email_available'),
    (r'is_email_available_for_user/$', 'common.services.is_email_available_for_user'),
    (r'is_username_available/$', 'common.services.is_username_available'),
    url(r'is_user_authenticated/$', 'common.services.is_user_authenticated', name="is_user_authenticated"),
    url(r'is_token_valid/$', 'common.services.is_token_valid', name="is_token_valid"),
    url(r'get_messages/$', 'common.services.get_messages', name="get_messages"),
    (r'get_polygons/$', 'common.services.get_polygons'),
    (r'update_city_area_order/$', 'common.services.update_city_area_order'),
    (r'init_(?P<model_name>\w+)_order/$', 'common.services.init_model_order'),
    (r'eval_src/$', 'common.maintenance.eval_src'),
    (r'run_task/$', 'common.maintenance.run_maintenance_task'),
    (r'run_task_on_queue/$', 'common.maintenance.maintenance_task'),

    (r'maintenance/weekly/$', 'common.maintenance.weekly'),
    (r'maintenance/fleet_manager_test/$', 'common.maintenance.fleet_manager_test'),
    (r'maintenance/billing_service_test/$', 'common.maintenance.run_billing_service_test'),
    (r'maintenance/routing_service_test/$', 'common.maintenance.run_routing_service_test'),
    (r'maintenance/routing_service_test_task/$', 'common.maintenance.test_routing_service_task'),
    (r'maintenance/gcp_service_test/$', 'common.maintenance.run_gcp_service_test'),
    (r'maintenance/gcp_service_test_task/$', 'common.maintenance.test_gcp_service_task'),

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
    (r'flush_memcache/$', 'common.geocode.flush_memcache'),
    (r'get_async_computation_result/$', 'common.views.get_async_computation_result'),
    url(r'get_terms/$', direct_to_template, {'template': "terms_form.html"} ,name="terms_dialog"),
    url(r'map_provider_loader\.js/$', direct_to_template, { 'template': "map_provider_loader.js",
                                                            'extra_context': {
                                                                "map_provider_url": settings.MAP_PROVIDER_LIB_URL,
                                                                "map_password":     settings.TELMAP_API_PASSWORD,
                                                                "map_username":     settings.TELMAP_API_USER
                                                            },
                                                            'mimetype': 'text/javascript' }),

    # services
    (r'^services/confirm_sms/$', 'common.sms_notification.confirm_sms'),
    (r'^services/osrm_proxy/(?P<service_name>\w+)/$', 'common.geocode.osrm_proxy'),

    # cron
    (r'^cron/calc_counters/$', 'common.cron.calc_counters'),

)

