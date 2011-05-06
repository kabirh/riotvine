# Django settings for riotvine project.
import os

DEBUG = True
#------- Local settings ---------------------
try:
    from mode_settings import *
except ImportError:
    pass # no local settings

TEMPLATE_DEBUG = DEBUG

ADMINS = (
    ('RiotVine Webmaster', 'admin@riotvine.com'),
)

MANAGERS = ADMINS

if not DEBUG:
    DATABASE_ENGINE = 'postgresql_psycopg2'           # 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
DATABASE_NAME = 'rvine'             # Or path to database file if using sqlite3.
DATABASE_USER = 'postgres'             # Not used with sqlite3.
DATABASE_PASSWORD = ''         # Not used with sqlite3.
DATABASE_HOST = 'db'             # Set to empty string for localhost. Not used with sqlite3.
DATABASE_PORT = '5433'             # Set to empty string for default. Not used with sqlite3.

TIME_ZONE = 'America/New_York'
LANGUAGE_CODE = 'en-us'
SITE_ID = 1
USE_I18N = True

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = '/home/web/public/media/'

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = '/media/'

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/admin-media/'

SECRET_KEY = 'p_gmyy9$_wix_p&8ivne^zxl^qe4#d$0ygyu_a$60t2a-y2t)g'

TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.load_template_source',
    'django.template.loaders.app_directories.load_template_source',
)

MIDDLEWARE_CLASSES = [
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.csrf.CsrfResponseMiddleware',
    'middleware.ProxyMiddleware',
    'middleware.SSLRedirectMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'mobile.middleware.MobileMiddleware',
    'middleware.ThreadNameMiddleware',
    'middleware.UserProfileMiddleware',
    'event.middleware.LocationMiddleware',
    'event.middleware.AnonymousEventMiddleware',
    'registration.middleware.SignUpMiddleware',
    'fb.middleware.FBMiddleWare',
    'pagination.middleware.PaginationMiddleware',
    # 'artist.middleware.ArtistRedirectorMiddleware',
    "django.contrib.flatpages.middleware.FlatpageFallbackMiddleware",
]

#if DEBUG:
#    MIDDLEWARE_CLASSES.append('django.middleware.doc.XViewMiddleware')

ROOT_URLCONF = 'irock_urls'

TEMPLATE_DIRS = ()

INSTALLED_APPS = (
    'website',
    'amqp',
    'common',
    'registration',
    'artist',
    'campaign',
    'event',
    'siteconfig',
    'queue',
    'payment',
    'messages',
    'photo',
    'oembed',
    'twitter',
    'pagination',
    'linker',
    'fb',
    'mobile',
    'fsq',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.flatpages',
    'django.contrib.admin',
    'django.contrib.markup',
    'django.contrib.formtools',
    'django.contrib.comments'
)

#------- Additional Django settings --------

TEMPLATE_CONTEXT_PROCESSORS = (
    "django.core.context_processors.auth",
    "django.core.context_processors.debug",
    "django.core.context_processors.i18n",
    "django.core.context_processors.request",
    "django.core.context_processors.media",
    "context_processors.customsettings.user_profile",
    "context_processors.customsettings.ui_vars",
    "context_processors.customsettings.extra",
    "context_processors.customsettings.admin_media",
    "context_processors.customsettings.admin_base",
    "context_processors.customsettings.hostname_port",
    "context_processors.customsettings.social",
    "context_processors.customsettings.social_user_agent",    
    "context_processors.extendedcontext.messages",
    "fb.context_processors.facebook",
    "common.context_processor.messages",
)

AUTHENTICATION_BACKENDS = (
    'backend.auth.emailauth.EmailBackend',
)

SERVER_EMAIL = 'RiotVine <root@riotvine.com>'
DEFAULT_FROM_EMAIL = 'RiotVine <feedback@riotvine.com>'
EMAIL_HOST = 'smtp' # '127.0.0.1'
EMAIL_SUBJECT_PREFIX = u'[RiotVine] '
SEND_BROKEN_LINK_EMAILS = (not DEBUG)
IGNORABLE_404_ENDS = ('favicon.ico', 'favicon.ico/', '.php', '.php/')
USE_ETAGS = True
SESSION_COOKIE_AGE = 100*24*60*60 # in seconds
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
LOGIN_REDIRECT_URL = '/'
AUTH_PROFILE_MODULE = 'registration.userprofile'
FORCE_SCRIPT_NAME = ''
LOGIN_URL = '/accounts/sign-in/'

if not DEBUG:
    CACHE_BACKEND = 'memcached://10.245.70.127:11211;10.242.58.3:11211/'

DATE_FORMAT = "N j, Y"

SESSION_COOKIE_DOMAIN = '.riotvine.com'

#------- Custom settings -------------------
from custom_settings import *

#------- Developer overrides ----------------
if DEBUG == True:
    from dev_settings import *
    if os.name == 'nt':
        from dev_nt_settings import *

#------- Local settings ---------------------
try:
    from local_settings import *
except ImportError:
    pass # no local settings

