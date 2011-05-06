DEV_MODE = False
LOG_DEBUG = True

DISPLAY_SITE_DOMAIN = 'riotvine.com'

STRF_DATE_FORMAT = "%b %d, %Y" # e.g. Aug 08, 2008
STRF_TIME_FORMAT = "%I:%m %p %Z" # e.g. 10:01 PM EST
STRF_DATETIME_FORMAT = "%b %d, %Y at %I:%m %p %Z" # Aug 08, 2008 at 10:01 PM EST

# These are made available as standard template variables via 
# context_processors.customsettings.ui
UI_SETTINGS = dict(
    UI_SITE_TITLE = 'RiotVine',
    UI_SITE_TITLE_UNBROKEN = 'RiotVine',
    UI_SITE_TAGLINE = 'RiotVine is your best source for event networking',
    UI_JS_VERSION = '6.5',
    UI_CSS_VERSION = '13.1',
    UI_DEV_MODE = DEV_MODE,
    UI_CACHE_TIMEOUT = '300',
    UI_PORT = '',
    UI_GOOGLE_ANALYTICS_CODE = 'UA-11551677-1', # 'UA-5332137-4',
    UI_SITE_DOMAIN = DISPLAY_SITE_DOMAIN,
    UI_SITE_COPYRIGHT = 'Copyright &copy; 2009-2010 RiotVine, Inc. All rights reserved.',
    UI_REGISTRATION_DEACTIVATION_THRESHOLD_DAYS = 7,
)

PROXY_ENABLED = True # Leave this as is on the production server
SSL_ENABLED = True # Leave this as is on the production server

UI_ROOT = '../../home/web/public/ui/' # Filesystem path relative to media root

# Absolute ADMIN base url
ADMIN_BASE = '/admin'

# These are made available as standard template variables via 
# context_processors.customsettings.extra
EXTRA_CONTEXT_SETTINGS = dict(
    EMAIL_SIGNATURE = '''Cheers,
The RiotVine Team
http://%s/''' % DISPLAY_SITE_DOMAIN,
)

MESSAGE_EMAIL_NOTIFICATION_ENABLED = True

ARTIST_REDIRECT_FIELDNAME = 'artist_next' # This is used by application code. Leave it as is.
ARTIST_REGISTRATION_NEXT = 'create_campaign' # Where an artist is redirected after registration

# When a short name for the artist/band is called for, 
# this setting is used to trim a longer name.
ARTIST_SHORT_NAME_LENGTH = 24


AVATAR_IMAGE_MAX_SIZE_MB = 3 # in MB
AVATAR_IMAGE_CROP = (48, 48) # Avatars are cropped to exactly this size.
AVATAR_MEDIUM_IMAGE_CROP = (60, 60) # Medium-sized avatars
AVATAR_DEFAULT_URL = 'images/default_profile.jpg' # Relative to MEDIA_URL/ui
AVATAR_MEDIUM_DEFAULT_URL = 'images/default_profile_medium.jpg' # Relative to MEDIA_URL/ui

# Which email addresses get the campaign approval request email.
CAMPAIGN_APPROVERS = (
    ('Riot Vine Admin', 'kabir@riotvine.com'),
    ('Riot Vine Admin', 'admin@riotvine.com'),
)
EVENT_APPROVERS = CAMPAIGN_APPROVERS

EVENT_MAX_PHOTOS_PER_MEMBER = 3

# How large an image file size do we allow to be uploaded to the campaign badge
CAMPAIGN_IMAGE_MAX_SIZE_MB = 3
EVENT_IMAGE_MAX_SIZE_MB = 3
EVENT_BG_IMAGE_MAX_SIZE_MB = 3

# A value lower than this is not allowed in a campaign's max contributors field
CAMPAIGN_MAX_CONTRIBUTORS_MIN_VALUE = 1

# A value lower than this is not allowed in a campaign's contribution amount field. In US Dollars.
# This must be a string and not a float.
CAMPAIGN_CONTRIBUTION_AMOUNT_MIN_VALUE = "1.00"

# The minimum age requirement for a campaign must be within this range if 
# the campaign has an age restriction.
CAMPAIGN_MIN_AGE_RANGE = (13, 130)
EVENT_MIN_AGE_RANGE = (13, 130)

# How many words of a campaign title to show in summary lists that need to 
# trim very long titles
CAMPAIGN_SHORT_TITLE_WORDS = 15
EVENT_SHORT_TITLE_WORDS = 15

# When a short name for the campaign is required, this setting is used to trim a longer name.
# Note that the badge generator automatically calculates its truncation limit based on the 
# font face and font size. So, this setting is not used in a badge.
CAMPAIGN_SHORT_TITLE_LENGTH = 25 # in characters not words
EVENT_SHORT_TITLE_LENGTH = 25 # in characters not words

# How many campaigns per page are shown on the campaign listing screen.
CAMPAIGNS_PER_PAGE = 5
EVENTS_PER_PAGE = 5

# Campaign badge generator settings
CAMPAIGN_BADGE_ARTIST_FONT = '/home/web/fonts/truetype/ms/arial.ttf'
CAMPAIGN_BADGE_ARTIST_FONT_SIZE = 12
CAMPAIGN_BADGE_ARTIST_POSITION = (12, 12) # (x, y)

CAMPAIGN_BADGE_TITLE_FONT = '/home/web/fonts/truetype/ms/arialbd.ttf'
CAMPAIGN_BADGE_TITLE_FONT_SIZE = 12
CAMPAIGN_BADGE_TITLE_POSITION = (0, 0) # (dx, xy) - relative to end of CAMPAIGN_BADGE_ARTIST_POSITION
CAMPAIGN_BADGE_TITLE_MAX_LINES = 3 # How many lines to break a long Campaign title into.
CAMPAIGN_BADGE_TITLE_CLEARANCE = 8 # Margin to prevent bleeding of title into the call out box

CAMPAIGN_BADGE_TEXT_FONT = '/home/web/fonts/truetype/ms/arialbd.ttf'
CAMPAIGN_BADGE_TEXT_FONT_SIZE = 12
CAMPAIGN_BADGE_TEXT_POSITION = (0, 0) # (dx, dy) - relative to end of CAMPAIGN_BADGE_TITLE_POSITION

CAMPAIGN_BADGE_JPEG_QUALITY = 100
CAMPAIGN_BADGE_IMAGE_POSITION = (6, 80) # (x, y) # The artist provided image gets inserted here.

CAMPAIGN_BADGE_CALLOUT_POSITION = (156, 6) # (x, y)

# Badge image templates
CAMPAIGN_BADGE_BACKGROUND_IMAGE_INTERNAL = 'badge_internal.jpg' # 233 x 247
CAMPAIGN_BADGE_BACKGROUND_IMAGE_EXTERNAL = 'badge_external.jpg' # 233 x 332
CAMPAIGN_BADGE_CALLOUT_IMAGE = 'badge_callout_box.jpg' # 67 x 53: The green how-you-can-help box at the top right


# (width, height) limits for campaign badges, avatars, and other images
CAMPAIGN_RESIZED_IMAGE_BOUNDING_BOX = (221, 162)
CAMPAIGN_AVATAR_IMAGE_CROP = AVATAR_IMAGE_CROP

#---- Event settings ----------
EVENT_BADGE_SPECIAL_FONT = '/home/web/fonts/truetype/ms/arial.ttf'
EVENT_BADGE_SPECIAL_FONT_SIZE = 10
EVENT_BADGE_SPECIAL_POSITION = (6, 130) # (x, y)

EVENT_BADGE_DATE_FONT = '/home/web/fonts/truetype/ms/arialbd.ttf'
EVENT_BADGE_DATE_FONT_SIZE = 16
EVENT_BADGE_DATE_POSITION = (10, 160) # (x, y)

EVENT_BADGE_ATTENDEE_FONT = '/home/web/fonts/truetype/ms/arialbd.ttf'
EVENT_BADGE_ATTENDEE_FONT_SIZES = (48, 36, 24)
EVENT_BADGE_ATTENDEE_POSITION = (10, 222) # (x, -y) -- y is the baseline position

EVENT_BADGE_TEXT_FONT = '/home/web/fonts/truetype/ms/arialbd.ttf'
EVENT_BADGE_TEXT_FONT_SIZE = 13
EVENT_BADGE_TEXT_POSITION = (5, 225) # (x, y)

EVENT_BADGE_JPEG_QUALITY = 99
EVENT_BADGE_IMAGE_POSITION = (78, 1) # (x, y) # The artist provided image gets inserted here.

# Badge image templates
EVENT_BADGE_BACKGROUND_IMAGE_INTERNAL = 'badge_event_internal.png' # 233 x 247
EVENT_BADGE_BACKGROUND_IMAGE_EXTERNAL = 'badge_event_external.png' # 233 x 332
# EVENT_BADGE_CALLOUT_IMAGE = 'badge_event_callout_box.jpg' # 67 x 53: The green how-you-can-help box at the top right
# (width, height) limits for campaign badges, avatars, and other images
EVENT_RESIZED_IMAGE_BOUNDING_BOX = (153, 245)

EVENT_BADGE_DEFAULT_IMAGE = 'badge_event_default.jpg' # 220 x 220
EVENT_RESIZED_IMAGE_BOUNDING_BOX = (211, 2000)
EVENT_AVATAR_IMAGE_CROP = (50, 50)
EVENT_AVATAR_IMAGE_SQUARE_CROP = (200, 200)
EVENT_AVATAR_IMAGE_SQUARE_MEDIUM_CROP = (110, 110)

EVENT_MAX_TWEETS = 50 # Maximum number of tweets to display on the page.

# The number of days beyond campaign's end date that a ticket may be redeemed.
# This is not enforced but is used in the "print tickets" screen to show the 
# appropriate redeem by date.
CAMPAIGN_TICKET_REDEEM_BY_GRACE_DAYS = 1

# A scheduled action item that doesn't complete in this time is resubmitted
QUEUE_TIMEOUT_MINUTES = 7

# How long is one invocation of the queue processing script allowed to run
QUEUE_SCRIPT_MAX_TIME_MINUTES = 5

# Action items completed this long ago are deleted from the system.
QUEUE_PURGE_TIME_DAYS = 7

# Processor implementations for various `ActionItem.category` values.
QUEUE_REGISTERED_PROCESSORS = {
    # 'campaign':'campaign.queue_processor.CampaignProcessor',
    # 'contribution':'campaign.queue_processor.ContributionProcessor',
    # 'event':'event.queue_processor.EventProcessor',
    'attendee':'event.queue_processor.AttendeeProcessor',
    'eventcheckin':'event.queue_processor.CheckinProcessor',
}


#
# The following three QUEUE_*_CHOICES are used by the queue.models.ActionItem
# model class. It's not recommended to change existing values but you can 
# add new values when required.
# 
# This is not modelled as database tables because:
#
# 1. that opens the possibility of 
#    an admin changing existing values more easily and causing the campaign workflow
#    processing of the application to break down.
#
# 2. it's not expected for this reference data to change 
#    in future (QUEUE_ACTION_CHOICES is the only param that may have 
#    some additions in future.)
# 
QUEUE_CATEGORY_CHOICES = (
                          # ('campaign', 'Campaign'),
                          # ('artist', 'Artist'),
                          # ('fan', 'Fan'),
                          # ('contribution', 'Contribution'),
                          ('admin', 'Admin'),
                          ('event', 'Event'),
                          ('attendee', 'Attendee'),
                          ('eventcheckin', 'EventCheckin'),
                          )

# QUEUE_ACTION_CHOICES = (('generate-tickets', 'Generate Tickets'),
#                        ('recompute-campaign', 'Recompute Campaign'),
#                        ('generate-badges', 'Generate Badges'),
#                        ('ack-contribution', 'Acknowledge Contribution'),
#                        ('approve-campaign', 'Approve Campaign'),
#                        ('approve-campaign-edit', 'Approve Campaign Edit'),
#                        ('merge-campaign-edits', 'Merge Campaign Edits'),
#                        ('email-campaign-approval', 'Email Campaign Approval'),
#                        ('delete-campaign', 'Delete Campaign'),
#                        ('print-tickets', 'Print Tickets'),
#                        ('send-payout', 'Send Payout'),
#                        ('misc-admin', 'Miscellaneous'),
#                        ('approve-event', 'Approve Event'),
#                        ('approve-event-edit', 'Approve Event Edit'),
#                        ('merge-event-edits', 'Merge Event Edits'),
#                        ('email-event-approval', 'Email Event Approval'),
#                        ('delete-event', 'Delete Event'),
#                        ('recompute-event', 'Recompute Event'),
#                        ('ack-attendee', 'Acknowledge Attendee'),)

QUEUE_ACTION_CHOICES = (
        ('event-faved', 'Send Friend Faved Email'),
        ('event-unlocked', 'Send Event Unlocked Email'),
)

# The port used by the queue script to ensure that only one instance of the 
# queue processor script is running at any time. If this is not defined, 
# multiple instances of the script are allowed to run on the same server.
#
# QUEUE_SCRIPT_LOCK_PORT = 55191

HOMEPAGE_INTRO_IMAGE_DIMENSIONS = (478, 241)

PHOTO_THUMBNAILS_PER_PAGE = 30
PHOTO_MAX_SIZE_MB = 3

# Only USD is currently supported, but the following currency parameters are here 
# for possible future use.
CURRENCIES_SUPPORTED = ('USD',) 
CURRENCY_DEFAULT = 'USD'

OEMBED_SUPPORTED_SERVICES = (('video', 'Video'), ('audio', 'Audio'), ('rich', 'Rich'))

AUTHORIZEDOTNET_URL = ''
AUTHORIZEDOTNET_LOGIN = ''
AUTHORIZEDOTNET_TRAN_KEY = ''

PAYMENT_PROCESSOR_CLS = 'payment.processor.authorizedotnet.PaymentProcessor'

PAYPAL_POST_URL = 'https://www.paypal.com/cgi-bin/webscr'
PAYPAL_IPN_POST_URL = PAYPAL_POST_URL # This is where the IPN is posted back for verification
PAYPAL_REFERRAL_URL = 'https://www.paypal.com/us/mrb/pal=HHS2TST4VYQZ2'

GOOGLE_POST_URL = 'https://checkout.google.com/api/checkout/v2/checkoutForm/Merchant/'
GOOGLE_CHECKOUT_IMAGE_URL = 'http://checkout.google.com/buttons/checkout.gif?w=160&h=43&style=trans&variant=text&loc=en_US&merchant_id='
GOOGLE_REFERRAL_URL = 'http://checkout.google.com/sell?promo='

GOOGLE_VALIDATION_URL = 'https://checkout.google.com/api/checkout/v2/requestForm/Merchant/'

SOCIAL_CONTEXT_SETTINGS = dict(
    MYSPACE_POST_URL='http://www.myspace.com/index.cfm?fuseaction=postto',
    MYSPACE_POST_TYPE=2, # 2 -> Bulleting
    FACEBOOK_SHARER='http://www.facebook.com/sharer.php', # http://www.facebook.com/sharer.php?u=http%3A%2F%2Fwww.cnn.com%2F&t=CNN%26s+website
    TWITTER_SHARER='http://twitter.com/home', # http://twitter.com/home?status=Listen+to+XYZ
)

SOCIAL_USER_AGENTS = (
 'facebookexternalhit',
)

MP3_PLAYER_LIST = (
    'reverbnation.com',
    'projectopus.com',
    'www.imeem.com',
)

# Samples of allowed MP3 player embed code. The list of valid tags and attributes is derived from this markup.
MP3_ALLOWED_EMBED_CODE = u'''
<!-- Reverbnation: -->
<img style="visibility:hidden;width:0px;height:0px;" border=0 width=0 height=0 src="http://counters.gigya.com/wildfire/IMP/CXNID=2000002.0NXC/bT*xJmx*PTEyMzY2OTg*MzQzMDkmcHQ9MTIzNjY5ODQ*MTA4OSZwPTI3MDgxJmQ9bXVzaWNfcGxheWVyX2ZpcnN*X2dlbiZnPTEmdD*mbz*4NGJiZTg4NmIzZmY*MzUzYWYzNzZmNjUxMDk*YTE2ZQ==.gif" /><embed type="application/x-shockwave-flash" src="http://cache.reverbnation.com/widgets/swf/15/widgetPlayer.swf?emailPlaylist=artist_33907&backgroundcolor=EEEEEE&font_color=000000&shuffle=&autoPlay=false" height="228" width="434" /><br/><a href="http://www.reverbnation.com/c./a4/15/33907/Artist/0/User/link"><img alt="Artist" border="0" height="19" src="http://cache.reverbnation.com/widgets/content/15/footer.png" width="434" /></a><br/><img style="visibility:hidden;width:0px;height:0px;" border=0 width=0 height=0 src="http://www.reverbnation.com/widgets/trk/15/artist_33907//t.gif"><a href="http://www.quantcast.com/p-05---xoNhTXVc" target="_blank"><img src="http://pixel.quantserve.com/pixel/p-05---xoNhTXVc.gif" style="display: none" border="0" height="1" width="1" alt="Quantcast"/></a>

<!-- Project Opus: -->
<div style="width: 340px; line-height: 16px; background-color: #666; font-family: Arial, Helvetica, sans-serif; font-size: 10px; color: #fff; text-align: center;"><embed src="http://www.projectopus.com/play/solo_player.swf?playercolor=F57E20&playlist_url=http://www.projectopus.com/song/xspf/55843&uid=21485&nid=55843" width="340" height="90" swLiveConnect="true" quality="high" pluginspage="http://www.macromedia.com/go/getflashplayer" type="application/x-shockwave-flash"></embed><br /><a href="http://www.projectopus.com/players" target="_blank" style="color: #ffc;">Get your own FREE music player</a></div>
<div style="width: 420px; line-height: 16px; background-color: #666; font-family: Arial, Helvetica, sans-serif; font-size: 10px; color: #fff; text-align: center;"><embed src="http://www.projectopus.com/play/folio_player_420x240.swf?uid=32919&playercolor=3C4C54&display=playlists" width="420" height="240" swLiveConnect="true" quality="high" pluginspage="http://www.macromedia.com/go/getflashplayer" type="application/x-shockwave-flash"></embed><br /><a href="http://www.projectopus.com/music-player" target="_blank" style="color: #ffc;">Get your own FREE music player</a></div>
    
<!-- Imeem -->
<div style="width:300px;"><object width="300" height="110"><param name="movie" value="http://media.imeem.com/m/p2Kfi6Nu8T/aus=false/"></param><param name="wmode" value="transparent"></param><embed src="http://media.imeem.com/m/p2Kfi6Nu8T/aus=false/" type="application/x-shockwave-flash" width="300" height="110" wmode="transparent"></embed></object><div style="background-color:#E6E6E6;padding:1px;"><div style="float:left;padding:4px 4px 0 0;"><a href="http://www.imeem.com/"><img src="http://www.imeem.com/embedsearch/E6E6E6/" border="0"  /></a></div><form method="post" action="http://www.imeem.com/embedsearch/" style="margin:0;padding:0;"><input type="text" name="EmbedSearchBox" /><input type="submit" value="Search" style="font-size:12px;" /><div style="padding-top:3px;"><a href="http://www.imeem.com/ads/banneradclick.ashx?ep=0&ek=p2Kfi6Nu8T" rel="nofollow"><img src="http://www.imeem.com/ads/bannerad/152/10/" border="0" /></a><a href="http://www.imeem.com/ads/banneradclick.ashx?ep=1&ek=p2Kfi6Nu8T" rel="nofollow"><img src="http://www.imeem.com/ads/bannerad/153/10/" border="0" /></a><a href="http://www.imeem.com/ads/banneradclick.ashx?ep=2&ek=p2Kfi6Nu8T" rel="nofollow"><img src="http://www.imeem.com/ads/bannerad/154/10/" border="0" /></a><a href="http://www.imeem.com/ads/banneradclick.ashx?ep=3&ek=p2Kfi6Nu8T" rel="nofollow" ><img src="http://www.imeem.com/ads/bannerad/155/10/p2Kfi6Nu8T/" border="0" /></a></div></form></div></div><br/><a href="http://www.imeem.com/prettyandnice/music/YUP8G-vY/pretty-nice-tora-tora-tora/">Tora Tora Tora - Pretty & Nice</a>

<!-- ustream.tv -->
<object classid="clsid:d27cdb6e-ae6d-11cf-96b8-444553540000" width="480" height="386" id="utv47717" name="utv_n_972940"><param name="flashvars" value="autoplay=false" /><param name="allowfullscreen" value="true" /><param name="allowscriptaccess" value="always" /><param name="src" value="http://www.ustream.tv/flash/video/2436564" /><embed flashvars="autoplay=false" width="480" height="386" allowfullscreen="true" allowscriptaccess="always" id="utv47717" name="utv_n_972940" src="http://www.ustream.tv/flash/video/2436564" type="application/x-shockwave-flash" /></object> 
'''


MP3_URL_PLAYER = u'''
<iframe frameborder="0" scrolling="no" width="300" height="28" src="http://www.google.com/reader/ui/3247397568-audio-player.swf?audioUrl=%(mp3_url)s">
</iframe>
'''
# <embed type="application/x-shockwave-flash" src="http://www.google.com/reader/ui/3247397568-audio-player.swf?audioUrl=%(mp3_url)s" width="300" height="27" allowscriptaccess="never" quality="best" bgcolor="#ffffff" wmode="window" flashvars="playerMode=embedded" />

TWITTER_CONSUMER_KEY = 'cVb3zHMKXmL9qYcgH1bQVQ' # IR: 'WAAadOKYwh5QcdGdoiqQ'
TWITTER_CONSUMER_SECRET = 'RaRN3iqI3q7Xtpqjsz4Rdsyudqq8hyy3Z0Hkikl1Y' # IR: 'A4IBzs6r1jRGhXcbO3kRysSppjuVP1Bt3G8x74a8tCk'
TWITTER_OAUTH_CALLBACK_URL = 'http://riotvine.com/twitter/callback/'

TWITTER_GENERAL_STATUS_FORMAT = u'%(status)s'
TWITTER_EVENT_STATUS_FORMAT = u"%(event_name)s! %(event_url)s"
TWITTER_EVENT_NAME_MAX_LENGTH = 100
TWITTER_SLEEP = .02 # throttle GET API calls
TWITTER_SEARCH_SLEEP = .1 # 100 millisecond sleep
TWITTER_SEARCH_RETRY_TIMES = 1 # Perform one retry if the search call gets throttled
TWITTER_BAD_HASHTAGS = (
    '!!',
)

USER_AGENT = 'RiotVine v/1.0'

FACEBOOK_HOMEPAGE = u'http://www.facebook.com/pages/RiotVine/100823595137'

# u"http://ticketsus.at/illiusrock?CTY=37&DURL=%(url)s"
TICKETMASTER_URL = u"http://ticketsus.at/RiotVine?CTY=37&LID=99&DURL=%(url)s"
# Search example: http://www.ticketmaster.com/search?q=beacon+theatre+new+york+lyle+lovett+and+his+large+band
TICKETMASTER_SEARCH_URL = u'http://www.ticketmaster.com/search?%s'
TICKETMASTER_JSON_SEARCH_URL = u'http://www.ticketmaster.com/json/search/event/national?%s'


#TINY_URL_API = u"http://tinyurl.com/api-create.php"
TINY_URL_API = u"http://api.bit.ly/shorten"
BITLY_API_LOGIN = 'riotvine'
BITLY_API_KEY = 'R_b4c12ebb97e9e030d35cd2bf61928252' # IR: 'R_9ff0736230fcdafc377f77f01530e291'

LASTFM_SCRIPT_LOCK_PORT = 10912
LASTFM_API_KEY = '5aac89fcb6ec2052e7f8d33b0a6a39b2'
LASTFM_API_SECRET = '888d60a1101f37a676899d7cc3c24cf5'
LASTFM_API_URL = 'http://ws.audioscrobbler.com/2.0/' # format=json&api_key=xxx
LASTFM_MAX_PAGES = 200
LASTFM_UPDATE_EXISTING = False

# http://code.google.com/apis/ajaxsearch/documentation/reference.html#_intro_fonje
# http://ajax.googleapis.com/ajax/services/search/local?v=1.0&mrt=blended&sll=42.364805,-71.105604&rsz=large&q=QUERY'
GOOGLE_LOCAL_SEARCH_URL = u'http://ajax.googleapis.com/ajax/services/search/local?%s' 
GOOGLE_LOCAL_CENTER = '42.358919,-71.057803'
GOOGLE_LOCAL_REFERER = 'http://riotvine.com/'
GOOGLE_LOCAL_DIRECT_URL = u'http://maps.google.com/local?%s' # http://www.google.com/local?q=Andala+Cafe&sll=42.364805,-71.105604
VENUE_DEFAULT_GEO_LOC = GOOGLE_LOCAL_CENTER

AMQP_HOST = 'amqp'
AMQP_USERID = 'guest'
AMQP_PASSWORD = 'guest'
COUCHDB_SERVER = 'http://localhost:5984'

TASK_LOCK_PORT = {
    'twitter.make_friends':10124,
    'event.make_recommendations':10134,
    'event.send_reminders':10144,
    'event.fetch_all_event_tweets':10150,
    'event.fetch_current_event_tweets':10150,
    'event.eventcreatedsignals':10160,
    'event.do_fsq_venues':10170,
}

AWS_QUERYSTRING_EXPIRE = 3600 * 24 * 365 # in seconds
from email.Utils import formatdate
import time
exp = formatdate(time.time() + AWS_QUERYSTRING_EXPIRE)[:26] + "GMT"  # +1 year
AWS_HEADERS = {
    'Expires': exp, # 'Thu, 15 Apr 2010 20:00:00 GMT' see http://developer.yahoo.com/performance/rules.html#expires
}
AWS_STORAGE_BUCKET_NAME = 'riotvine'
# from django_storages.S3 import CallingFormat
# AWS_CALLING_FORMAT = CallingFormat.SUBDOMAIN
AWS_ASSOCIATE_TAG = u'riot06-20'

TWITTER_GEOIP_ENABLED = True
TWITTER_SEARCH_DISTANCE = '60km'

LOCATIONS = (
    ('austin', 'Austin, TX'),
    ('boston', 'Boston, MA'),
    ('losangeles', 'Los Angeles, CA'),
    ('newyork', 'New York, NY'),
    ('sanfrancisco', 'San Francisco, CA'),
    ('destination', 'Destination'),
    ('user-entered', 'User Entered'),
)
LOCATION_DEFAULT = 'boston'
LOCATION_MAP = dict(LOCATIONS)
LOCATION_DATA = {
    'boston':(42.63699, -71.549835, 'Boston,+United+States', 'Boston', 'ET'), # lat, lng, lastfm loc, name, tz
    'losangeles':(34.052179, -118.243425, 'Los+Angeles,+United+States', 'Los Angeles', 'PT'),
    'newyork':(40.754539, -73.987427, 'New+York,+United+States', 'New York', 'ET'),
    'sanfrancisco':(37.779127,-122.419968, 'San+Francisco,+United+States', 'San Francisco', 'PT'),
    'austin':(30.267203,-97.743065, 'Austin,+United+States', 'Austin', 'CT'),
}


EMPTY_LOCATION_DATA = (0, 0, '', '', '')
LOCATION_SUBDOMAIN_MAP = {
    'ny':'newyork',
    'la':'losangeles',
    'boston':'boston',
    'sf':'sanfrancisco',
    'austin':'austin',
}
LOCATION_SUBDOMAIN_REVERSE_MAP = {
    'newyork':'ny',
    'losangeles':'la',
    'boston':'boston',
    'sanfrancisco':'sf',
    'austin':'austin',
}
STATE_TO_LOCATION_MAP = {
    'ma': 'boston',
    'massachusetts':'boston',
    'ny':'newyork',
    'nj':'newyork',
    'new york':'newyork',
    'new jersey':'newyork',
    'ca':'losangeles',
    'california':'losangeles',
    'tx':'austin',
    'texas':'austin',
}
CITY_STATE_TO_LOCATION_MAP = {
    'san francisco|ca':'sanfrancisco',
    'san francisco|california':'sanfrancisco',
}

LOCATION_COOKIE_NAME = 'RIOTVINE_LOC'
LOCATION_COOKIE_AGE_SECONDS = 3600 * 24 * 31 # Remember location for 31 days
LOCATION_GEOIP_PATH = '../geoip-data/GeoLiteCity.dat'

CALENDAR_FILTER_BY_LOCATION = True
RECOMMENDED_EVENTS_FILTER_BY_LOCATION = True

EVENT_CLEANUP_DAYS_MIN = 14
EVENT_CLEANUP_DAYS_MAX = 16

UTC_TIME_DIFFERENCE = 4 # EDT
# UTC_TIME_DIFFERENCE = 5 # EST

# Whether to use the tweetimag.es service for Twitter profile images. If set to False, 
# normal S3 URLs will be used for profile images. These URLs break whenever a 
# profile changes.
TWITTER_USE_TWEETIMAGES = True

GCAL_ADD_EVENT_URL = u'http://www.google.com/calendar/event'

BADGE_VERSION = "1.0"
BADGE_CODE_TYPE = "IFRAME" # Possible values "IFRAME", "JAVASCRIPT"

FB_APP_ID = '193465379012'
FB_API_KEY = 'a012e9eb9c2253c0c54565652927a987'

REGISTRATION_DEACTIVATION_THRESHOLD_DAYS = UI_SETTINGS['UI_REGISTRATION_DEACTIVATION_THRESHOLD_DAYS'] # deactivate accounts not confirmed within this time period

FB_AUTO_FRIEND = True

MOBILE_USER_AGENTS = (
    ('iphone;', 'iphone'),
    ('android ', 'android'),
    (' pre/', 'pre'),
    # ('Opera Mini/5.0'.lower(), 'opera'),
)

from datetime import date, datetime, timedelta
now = datetime.now() + timedelta(hours=1)
if now.date() < date(2010, 3, 22):
    MOBILE_HOMEPAGE_CITIES = [
        '<a href="http://austin.riotvine.com/event/search/?q=%23sxsw">Unofficial SXSW Guide!<span class="arrow">&nbsp;&raquo;</span></a>',
    ]
    UI_SETTINGS['UI_SXSX_ENABLED'] = True

ACCOUNT_EMAIL_VERIFICATION_DEFAULT = True # Assume email is verified

CHECKIN_THRESHOLD_MINUTES = 80 # How many minutes before an event's start time should checkin stats be shown

FOURSQUARE_USER_AGENT = 'RiotVine:10.03.18 RiotVine/1.0'

SPORTS_TEAM_TEXT_START = 0, 50
SPORTS_TEAM_TEXT_FONT = '/home/web/fonts/ariblk.ttf'
SPORTS_TEAM_TEXT_FONT_SIZE = 24
SPORTS_TEAM_TEXT_SMALL_FONT_SIZE = 20

EVENT_SEARCH_NORMALIZATION = {
    'mlb2010':'baseball'
}

FOURSQUARE_UNLOCK_SUBJECT = u'Great to see you out and about!'
FOURSQUARE_UNLOCK_BETA = True
