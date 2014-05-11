# -*- coding: utf-8 -*-

# Initialize App Engine and import the default settings (DB backend, etc.).
# If you want to use a different backend you have to remove all occurrences
# of "djangoappengine" from this file.
from djangoappengine.settings_base import *
import os
from localsettings import *

LOCAL = 'SERVER_SOFTWARE' not in os.environ or os.environ['SERVER_SOFTWARE'].lower().startswith('dev')
DEV_VERSION = 'CURRENT_VERSION_ID' in os.environ and os.environ['CURRENT_VERSION_ID'].lower().startswith('dev')
DEV = LOCAL or DEV_VERSION
DEBUG = DEV

DEFAULT_PROTOCOL = "https"
if LOCAL:
    DEFAULT_DOMAIN = 'localhost:8000'
elif DEV:
    DEFAULT_DOMAIN = '***REMOVED***'
else:
    DEFAULT_DOMAIN = '***REMOVED***'

if DEV_VERSION:
    WEB_APP_URL = "***REMOVED***"
else:
    WEB_APP_URL = "***REMOVED***"

CLOSE_CHILD_BROWSER_URI = "***REMOVED***"

# setup default datastore paths
base_dir = os.path.abspath(os.path.dirname('__file__'))
_ds_pathinfo = {
    'datastore_path': '../data/waybetter.datastore',
    'history_path': '../data/waybetter.datastore.history',
}
if "publish" in base_dir:
    for k in _ds_pathinfo.keys():
        _ds_pathinfo[k] = "../%s" % _ds_pathinfo[k]

DATABASES['default']['DEV_APPSERVER_OPTIONS'].update(_ds_pathinfo)
# Activate django-dbindexer for the default database
DATABASES['native'] = DATABASES['default']
DATABASES['default'] = {'ENGINE': 'dbindexer', 'TARGET': 'native'}
AUTOLOAD_SITECONF = 'indexes'


SECRET_KEY = '***REMOVED***'

INSTALLED_APPS = (
'djangotoolbox',
'autoload',
'dbindexer',
#    'django.contrib.auth',
'django.contrib.contenttypes',
'django.contrib.sessions',
'django.contrib.admin',
'flatpages2',
'openid_consumer',
'tinymce',
'socialauth',
'oauth2',
'registration',
'ajax_forms',
'common',
'geo',
'analytics',
'ordering',
'interests',
'testing',
'api',
'metrics',
'sharing',
'pricing',
'billing',
'fleet',
# djangoappengine should come last, so it can override a few manage.py commands
'djangoappengine',
)

MIDDLEWARE_CLASSES = (
# This loads the index definitions, so it has to come first
'autoload.middleware.AutoloadMiddleware',

#'google.appengine.ext.appstats.recording.AppStatsDjangoMiddleware', # uncomment to activate app stats
'common.middleware.URLRouting.URLRouting', # may redirect so should load early
'django.middleware.common.CommonMiddleware',
#'django.contrib.sessions.middleware.SessionMiddleware',
'common.middleware.session.SessionMiddleware',
'common.middleware.overrideBrowser.LanguageMiddleware',
'django.middleware.locale.LocaleMiddleware',
'django.middleware.csrf.CsrfViewMiddleware',
'django.contrib.auth.middleware.AuthenticationMiddleware',
'django.contrib.messages.middleware.MessageMiddleware',
'openid_consumer.middleware.OpenIDMiddleware',
'flatpages2.middleware.FlatpageFallbackMiddleware',
#'common.middleware.noCacheMiddleware.NoCacheMiddleWare',
'common.middleware.minidetector.Middleware',
'common.middleware.mobileSession.MobileSessionMiddleware',
#'common.middleware.modtimeurls.ModTimeUrlsMiddleware',
'common.middleware.station_domain_middleware.StationDomainMiddleware',
)

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.contrib.auth.context_processors.auth',
    'django.core.context_processors.debug',
    'django.core.context_processors.i18n',
    'django.core.context_processors.media',
    'django.core.context_processors.request',
    'django.contrib.messages.context_processors.messages',
    'common.middleware.minidetector.is_mobile_processor',
    'common.context_processors.dev'
)

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'oauth2.backends.FacebookBackend',
)

TEST_RUNNER = 'djangotoolbox.test.CapturingTestSuiteRunner'

# django settings
TEMPLATE_DEBUG = DEBUG
ADMIN_MEDIA_PREFIX = '/media/admin/'
MEDIA_ROOT = os.path.join(os.path.dirname(__file__), 'static')
MEDIA_URL = '/static/'
TEMPLATE_DIRS = (os.path.join(os.path.dirname(__file__), 'templates'),)
FIXTURE_DIRS = (os.path.join(os.path.dirname(__file__), 'testing/fixtures'),)

ROOT_URLCONF = 'urls'

ugettext = lambda s: s

LANGUAGES = (
    ('he', u'עברית'),
    ('en', u'English'),
    ('ru', u'Русский'),
    ('fr', u'français'),
)

DEFAULT_COUNTRY_CODE = "IL"
LANGUAGE_CODE = 'he'

# django-registration settings
ACCOUNT_ACTIVATION_DAYS = 2
#EMAIL_HOST = 'localhost'

# WAYbetter settings
INIT_TOKEN     = '***REMOVED***'
ADMIN_USERNAME = '***REMOVED***'
ADMIN_PASSWORD = '***REMOVED***'
ADMIN_EMAIL    = '***REMOVED***'
SUPPORT_EMAIL    = '***REMOVED***'
CONTACT_PHONE = "***REMOVED***"
NO_REPLY_SENDER = "***REMOVED***"
DEFAULT_FROM_EMAIL = '***REMOVED***'
LOGIN_REDIRECT_URL = '/'
STATION_LOGIN_URL = '/stations/login/'
SYSTEM_IM_USER = '***REMOVED***'
TIME_ZONE = 'UTC'
DATETIME_FORMAT = "d/m/y H:i"
POLLING_INTERVAL = 30000
MOBILE_SESSION_COOKIE_AGE = 31556926 # 1 year
BUILD_SERVICE_BASE_URL = "***REMOVED***"
NUMBER_OF_WORKSTATIONS_TO_CREATE = 2

# API's
CLOUDMADE_API_KEY = '***REMOVED***' #amir@waybetter.com
WAZE_API_TOKEN = '***REMOVED***'
TELMAP_API_USER = '***REMOVED***'
TELMAP_API_PASSWORD = '***REMOVED***'
MAP_PROVIDER_LIB_URL = '***REMOVED***'
GOOGLE_API_BROWSER_KEY = '***REMOVED***'


SMS_PROVIDER_URL            = "provider_url"
SMS_PROVIDER_USER_NAME      = "user_id"
SMS_PROVIDER_PASSWORD       = "user_password"
SMS_FROM_PHONE_NUMBER       = "originator"
SMS_FROM_MARKETING_NAME     = "marketing_sender_name"
SMS_FROM_MARKETING_PHONE    = "marketing_sender_phone"
SMS_VALIDITY_PERIOD         = "sms_validity_period"
SMS_CALLBACK_URL            = "sms_callback_url"
SMS_PROVIDER_FROM           = "from"

SMS = {
    SMS_PROVIDER_URL:           '***REMOVED***',
    SMS_PROVIDER_FROM:          '***REMOVED***',
    SMS_PROVIDER_USER_NAME:     '***REMOVED***',
    SMS_PROVIDER_PASSWORD:      '***REMOVED***',
    SMS_FROM_PHONE_NUMBER:      '***REMOVED***', # use account registered from-phone"
    SMS_FROM_MARKETING_NAME:    '***REMOVED***',
    SMS_FROM_MARKETING_PHONE:   '',
    SMS_VALIDITY_PERIOD:        1,
    SMS_CALLBACK_URL:           "%scommon/services/confirm_sms/" % WEB_APP_URL
}

TINYMCE_JS_URL = '%sjs/tiny_mce/tiny_mce.js' % MEDIA_URL
TINYMCE_DEFAULT_CONFIG = {
#    'plugins': "table,spellchecker,paste,searchreplace",
    'plugins': "table,paste,searchreplace, autoresize, directionality, preview, print, xhtmlxtras",
    'theme': "advanced",
    'cleanup_on_startup': True,
    'custom_undo_redo_levels': 10,
}
TINYMCE_SPELLCHECKER = False
TINYMCE_COMPRESSOR = False


INVOICE_INFO = {
    "invoice_url"               : "***REMOVED***",
    "invoice_username"          : "***REMOVED***",
    "invoice_key"               : "***REMOVED***",
    "invoice_password"          : "***REMOVED***", # for invoice4u web interface
    "invoice_counter"           : "passenger_invoice_id"
}

if DEV:
    # DEV settings
    BILLING = {
        "terminal_number"	        : "***REMOVED***",
        "terminal_number_no_CVV"	: "***REMOVED***",
        "username"			        : "***REMOVED***",
        "password"			        : "***REMOVED***",
        "url"                       : "***REMOVED***",
        "token_url"                 : "***REMOVED***",
        "transaction_url"           : "***REMOVED***",
    }
    BILLING_MPI = {
        "MID"               : "***REMOVED***",
        "userName"          : "***REMOVED***",
        "password"          : "***REMOVED***",
        "authNumber"        : 1234567, # used only for testing
    }
    BILLING_MPI_MOBILE = {
        "MID"               : "***REMOVED***",
        "userName"          : "***REMOVED***",
        "password"          : "***REMOVED***",
        "authNumber"        : 1234567, # used only for testing
    }

else:
    # production settings
    BILLING = {
        "terminal_number"	        : "***REMOVED***",
        "terminal_number_no_CVV"	: "***REMOVED***",
        "username"			        : "***REMOVED***",
        "password"			        : "***REMOVED***",
        "url"                       : "***REMOVED***",
        "token_url"                 : "***REMOVED***",
        "transaction_url"           : "***REMOVED***",
    }
    BILLING_MPI = {
        "MID"               : "***REMOVED***",
        "userName"          : "***REMOVED***",
        "password"          : "***REMOVED***",
        }

    BILLING_MPI_MOBILE = {
        "MID"               : "***REMOVED***",
        "userName"          : "***REMOVED***",
        "password"          : "***REMOVED***",
    }


# facebook settings
FACEBOOK_APP_URL = '***REMOVED***'
FACEBOOK_APP_ID = '***REMOVED***'
FACEBOOK_APP_SECRET = '***REMOVED***'
FACEBOOK_REDIRECT_URI = "http://%s%s" % (DEFAULT_DOMAIN, "/oauth2/facebook_login/")
FACEBOOK_CONNECT_URI = "https://graph.facebook.com/oauth/authorize"
FACEBOOK_LOGIN_LINK = "%s?client_id=%s&redirect_uri=%s&scope=email" % (FACEBOOK_CONNECT_URI, FACEBOOK_APP_ID, FACEBOOK_REDIRECT_URI)

TWITTER_APP_URL = 'http://twitter.com/WAYbetter_App'

# webapp settings
ANDROID_MARKET_APP_URL = "https://play.google.com/store/apps/details?id=com.waybetter.sharing"
APPLE_WAYBETTER_APP_ID = "485021829"
APPLE_WAYBETTER_ITUNES_URL = "http://itunes.apple.com/il/app/waybetter/id%s?mt=8&uo=4" % APPLE_WAYBETTER_APP_ID
APPLE_TESTER_PHONE_NUMBER = "***REMOVED***"
APPLE_TESTER_VERIFICATION = "***REMOVED***"

GA_ACCOUNT_ID = '***REMOVED***'