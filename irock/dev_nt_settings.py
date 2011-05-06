MEDIA_ROOT = '/JavaLib/etc/irock/media/'
EMAIL_HOST = '127.0.0.1'

DATABASE_ENGINE = 'sqlite3'           # 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
DATABASE_NAME = '../rvine.db'             # Or path to database file if using sqlite3.
DATABASE_USER = ''             # Not used with sqlite3.
DATABASE_PASSWORD = ''         # Not used with sqlite3.
DATABASE_HOST = ''             # Set to empty string for localhost. Not used with sqlite3.
DATABASE_PORT = ''             # Set to empty string for default. Not used with sqlite3.


UI_ROOT = '../src/trunk/ui/'

CAMPAIGN_BADGE_ARTIST_FONT = 'arialbd.ttf'
CAMPAIGN_BADGE_TITLE_FONT = 'arialbd.ttf'
CAMPAIGN_BADGE_TEXT_FONT = 'arialbd.ttf'
CAMPAIGN_BADGE_CALLOUT_FONT = 'arial.ttf'


EVENT_BADGE_SPECIAL_FONT = 'arialbd.ttf'
EVENT_BADGE_DATE_FONT = 'arialbd.ttf'
EVENT_BADGE_ATTENDEE_FONT = 'arialbd.ttf'
EVENT_BADGE_TEXT_FONT = 'arialbd.ttf'

DISABLE_EMAILS = True

MP3_URL_VERIFY_EXISTS = False

TWITTER_OAUTH_CALLBACK_URL = 'http://127.0.0.1:8000/twitter/callback/'
LASTFM_MAX_PAGES = 2

CACHE_BACKEND = 'file://c:/temp/cache'

ENABLE_SMTP_LOGGING = False

SUBDOMAIN_PORT = '8000'

DISPLAY_SITE_DOMAIN = '127.0.0.1'

EXTRA_CONTEXT_SETTINGS = dict(
    UI_DEV_MODE = True,
    UI_TEMPLATE_DEV_MODE = True,
    UI_GOOGLE_ANALYTICS_CODE = '',
    UI_SITE_DOMAIN = DISPLAY_SITE_DOMAIN,
    UI_PORT = u':' + SUBDOMAIN_PORT,
    EMAIL_SIGNATURE = '''Cheers,
The RiotVine Team
http://%s/''' % 'riotvine.com',
)

AMQP_HOST = '127.0.0.1'

SESSION_COOKIE_DOMAIN = '127.0.0.1'

