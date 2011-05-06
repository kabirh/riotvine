DEV_MODE = True

ADMINS = (
    ('RiotVine Webmaster', 'rajesh.dhawan@gmail.com'),
)

MANAGERS = ADMINS
CAMPAIGN_APPROVERS = ADMINS
EVENT_APPROVERS = ADMINS

DEV_ADMIN_MEDIA_ROOT = '/home/rajesh/workspace/python/django_trunk/django/contrib/admin/media/'
MEDIA_ROOT = '/home/rajesh/django-projects/irock/media/'
MEDIA_URL = '/media/'
EMAIL_HOST = 'mail.optonline.net'
INTERNAL_IPS = (
    "127.0.0.1",
    "172.16.95.113",
    "172.16.95.50",
    "172.16.95.51",
    "172.16.95.52",
    "172.16.95.53",
    "172.16.95.54",
    "172.16.95.55",
    "192.168.15.1",
    "192.168.15.100",
)

EXTRA_CONTEXT_SETTINGS = dict(
    UI_DEV_MODE = True,
    UI_TEMPLATE_DEV_MODE = True,
    UI_GOOGLE_ANALYTICS_CODE = '',
    EMAIL_SIGNATURE = '''Cheers,
The RiotVine Team
http://%s/''' % 'riotvine.com',
)

# Relative to media root
UI_ROOT = '../src/uat/ui/'

CAMPAIGN_BADGE_ARTIST_FONT = '/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf'
CAMPAIGN_BADGE_TITLE_FONT = '/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf'
CAMPAIGN_BADGE_TEXT_FONT = '/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf'
CAMPAIGN_BADGE_CALLOUT_FONT = '/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf'

CAMPAIGN_BADGE_TITLE_CLEARANCE = 10 # Margin to prevent bleeding of title into the call out box

EVENT_BADGE_SPECIAL_FONT = '/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf'
EVENT_BADGE_DATE_FONT = '/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf'
EVENT_BADGE_ATTENDEE_FONT = '/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf'
EVENT_BADGE_TEXT_FONT = '/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf'

EVENT_BADGE_TEXT_FONT_SIZE = 14
EVENT_BADGE_TITLE_CLEARANCE = 10 # Margin to prevent bleeding of title into the call out box


#CACHE_BACKEND = 'locmem:///'
CACHE_BACKEND = 'memcached://127.0.0.1:11211/'

PROXY_ENABLED = False
SSL_ENABLED = False

AUTHORIZEDOTNET_URL = 'https://test.authorize.net/gateway/transact.dll'
AUTHORIZEDOTNET_LOGIN = '6zz6m5N4Et'
AUTHORIZEDOTNET_TRAN_KEY = '9V9wUv6Yd92t27t5'

PAYPAL_RECEIVER_EMAIL_ADDRESS = 'rajesh_1215544425_biz@gmail.com' # This is only used during development
PAYPAL_POST_URL = 'https://www.sandbox.paypal.com/cgi-bin/webscr'
PAYPAL_IPN_POST_URL = PAYPAL_POST_URL

GOOGLE_MERCHANT_ID = '621898986949535' # Only used during development
GOOGLE_MERCHANT_KEY = 'KVTjh_w4ynfpGCp7oo7TtA' # Only used during development

GOOGLE_POST_URL = 'https://sandbox.google.com/checkout/api/checkout/v2/checkoutForm/Merchant/'
GOOGLE_CHECKOUT_IMAGE_URL = 'http://sandbox.google.com/checkout/buttons/checkout.gif?w=160&h=43&style=trans&variant=text&loc=en_US&merchant_id='

GOOGLE_VALIDATION_URL = 'https://sandbox.google.com/checkout/api/checkout/v2/requestForm/Merchant/'

TWITTER_CONSUMER_KEY = 'ttiDldQ2Fb4Ew8suWyDubA'
TWITTER_CONSUMER_SECRET = 'DbI6uajEBjSUBYZrqla1snmjx0bNBD4HXehm3mMR2Y'
TWITTER_OAUTH_CALLBACK_URL = 'http://piermontweb.dnsdojo.com:8020/twitter/callback/'

BITLY_API_LOGIN = 'rajeshdhawan'
BITLY_API_KEY = 'R_cfdda28021fe460d1af54f7f5ae0dde2'

LASTFM_API_KEY = '6479691adff7927d3ad6708d89c121f1'
LASTFM_API_SECRET = '95ec4cfefcd33d795499472ae86b8c9a'
LASTFM_MAX_PAGES = 5

AWS_QUERYSTRING_EXPIRE = 365*24*3600 # in seconds
from email.Utils import formatdate
import time
exp = formatdate(time.time() + AWS_QUERYSTRING_EXPIRE)[:26] + "GMT"  # +1 hour
AWS_HEADERS = {
    'Expires': exp, # 'Thu, 15 Apr 2010 20:00:00 GMT' see http://developer.yahoo.com/performance/rules.html#expires
}
AWS_STORAGE_BUCKET_NAME = 'riotvine-dev'
#
# Populate the following in local_settings:
#
# DEFAULT_FILE_STORAGE = 'django_storages.backends.s3boto.S3BotoStorage'
# AWS_ACCESS_KEY_ID = ''
# AWS_SECRET_ACCESS_KEY = ''
#
SESSION_COOKIE_DOMAIN = '.dnsdojo.com'

FB_APP_ID = '222955231367'
FB_API_KEY = '9fa2d6e8614088700a3a4acd7f206cdc'

