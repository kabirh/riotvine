from __future__ import absolute_import
import logging
import os.path
import random
import string
import textwrap
from uuid import uuid4
from time import time
from mimetypes import guess_type
from decimal import Decimal as D
from datetime import datetime, date, timedelta
import Image, ImageFont, ImageDraw
from BeautifulSoup import BeautifulSoup

from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile, UploadedFile
from django.db import models
from django.db import connection, transaction
from django.contrib.auth.models import User
from django.utils import simplejson as json
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _
from django.utils.safestring import mark_safe
from django.utils.http import urlencode
from django.utils.text import truncate_words
from django.utils import simplejson as json
from django.db.models import signals

from rdutils import chunks
from rdutils.url import admin_url, POPUP, get_tiny_url
from rdutils.site import DISPLAY_SITE_URL
from rdutils.cache import key_suffix, short_key, clear_keys, cache, shorten_key
from rdutils.image import get_raw_png_image, resize_in_memory, get_perfect_fit_resize_crop, remove_model_image, close, get_raw_image, str_to_file
from rdutils.decorators import attribute_cache
from rdutils.text import slugify
from rdutils.query import quote_name
from artist.models import ArtistProfile
from queue.models import ActionItem
from registration.models import Address, UserProfile
from photo.models import Photo
from oembed.models import ServiceProvider as OEmbedProvider
from twitter.utils import convert_timestamp, quote_hashtags
from event.utils import clean_address
from event.amqp import tasks
from event import signals as event_signals
from event import badgegen


_log = logging.getLogger('event.models')

_SUBDOMAIN_PORT = getattr(settings, 'SUBDOMAIN_PORT', '')
if _SUBDOMAIN_PORT:
    _SUBDOMAIN_PORT = u":" + _SUBDOMAIN_PORT
_UI_MEDIA_ROOT = os.path.join(settings.MEDIA_ROOT, settings.UI_ROOT, 'internal')
_BADGE_BG_IMAGE_INTERNAL = os.path.join(_UI_MEDIA_ROOT, settings.EVENT_BADGE_BACKGROUND_IMAGE_INTERNAL)
_BADGE_BG_IMAGE_EXTERNAL = os.path.join(_UI_MEDIA_ROOT, settings.EVENT_BADGE_BACKGROUND_IMAGE_EXTERNAL)
_MP3_URL_VERIFY_EXISTS = getattr(settings, 'MP3_URL_VERIFY_EXISTS', True)


def today_timedelta_by_location(location, timezone=None):
    tz = timezone or settings.LOCATION_DATA.get(location, settings.EMPTY_LOCATION_DATA)[4]
    tz = tz.upper()
    # normalize to CT, PT, ET
    if not tz:
        tz = 'ET'
    if tz[0] == 'C':
        tz = 'CT'
    elif tz[0] == 'P':
        tz = 'PT'
    else:
        tz = 'ET'
    if tz == 'CT':
        td = timedelta(hours=1)
    elif tz == 'PT':
        td = timedelta(hours=3)
    else:
        td = None
    today = td and (datetime.today() - td).date() or date.today()
    return today, td


class Venue(models.Model):
    VENUE_SOURCES = (
        ('google-maps', 'Google Maps'),
        ('last-fm', 'Last FM'),
        ('user-entered', 'User Entered'),
        ('mlb', 'MLB'),
    )
    VENUE_SOURCE_DEFAULT = 'user-entered'
    ZIPCODE_HELP = _('The 5-digit U.S. zip code where this event will take place.')

    name = models.CharField(_('event venue'), db_index=True, max_length=255, help_text=_('The location of this event. For example: Xaviers Cafe, 123 Street, Cambridge, MA'))
    alias = models.CharField(max_length=100, blank=True, db_index=True)
    source = models.CharField(max_length=30, db_index=True, choices=VENUE_SOURCES, default=VENUE_SOURCE_DEFAULT)
    geo_loc = models.CharField(max_length=255, db_index=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=255, db_index=True, blank=True)
    state = models.CharField(max_length=100, db_index=True, blank=True)
    zip_code = models.CharField('zip code', max_length=12, help_text=ZIPCODE_HELP, db_index=True, blank=True)
    map_url = models.URLField(max_length=255, verify_exists=False, blank=True, default='', editable=True)
    venue_url = models.URLField(max_length=255, verify_exists=False, blank=True, default='', editable=True, db_index=True)
    fsq_id = models.CharField(max_length=64, default='', blank=True, db_index=True, editable=True)
    fsq_checkins = models.IntegerField(default=0, null=True, blank=True, db_index=True, editable=True)
    fsq_ratio = models.CharField(max_length=25, default=u'', blank=True, db_index=True, editable=True)
    # internal ratios
    fsq_m = models.IntegerField(default=0, null=True, blank=True, db_index=True)
    fsq_f = models.IntegerField(default=0, null=True, blank=True, db_index=True)
    fsq_mf = models.DecimalField(blank=True, null=True, max_digits=10, decimal_places=2, db_index=True)
    fsq_fm = models.DecimalField(blank=True, null=True, max_digits=10, decimal_places=2, db_index=True)
    added_on = models.DateTimeField(default=datetime.now, editable=False, db_index=True)
    updated_on = models.DateTimeField(default=datetime.now, editable=False, db_index=True)

    class Meta:
        ordering = ('name',)
        unique_together = (('name', 'geo_loc'),)

    def __unicode__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.added_on:
            self.added_on = datetime.now()
        self.updated_on = datetime.now()
        if not self.map_url:
            url = settings.GOOGLE_LOCAL_DIRECT_URL
            adr = u', '.join([self.name, self.address, self.city, self.state])
            params = urlencode(dict(q=adr, sll=self.geo_loc or settings.GOOGLE_LOCAL_CENTER))
            self.map_url = (url % params)[:255]
        self.address, self.city, self.state, self.zip_code = clean_address(self.address, self.city, self.state, self.zip_code)
        if not self.fsq_mf:
            self.fsq_mf = 0
        if not self.fsq_fm:
            self.fsq_fm = 0
        if not self.fsq_m:
            self.fsq_m = 0
        if not self.fsq_f:
            self.fsq_f = 0
        super(Venue, self).save(*args, **kwargs)

    @property
    def params(self):
        """Return parameters in Google Local's JSON format"""
        lat, lng = self.geo_loc.split(",")
        p = dict(
            lat=lat,
            lng=lng,
            titleNoFormatting=self.name,
            streetAddress=self.address,
            city=self.city,
            region=self.state,
            url=self.map_url,
            addressLines=u"%s, %s, %s %s" % (self.address, self.city, self.state, self.zip_code),
        )
        return json.dumps(p)
    
    @property
    @attribute_cache('citystatezip')
    def citystatezip(self):
        c, sz = [], []        
        if self.city:
            c.append(self.city)
        if self.state:
            sz.append(self.state)
        #if self.zip_code:
        #    sz.append(self.zip_code)
        szstr = u' '.join(sz)
        if szstr:
            c.append(szstr)
        return ',' in self.city and u' '.join(c) or u', '.join(c)
    
    @property
    def alias_or_name(self):
        return self.alias or self.name
    
    @property
    @attribute_cache('fsq_ratio_display2')
    def fsq_ratio_display(self):
        r = u''
        if self.fsq_ratio and ':' in self.fsq_ratio:
            m, f = self.fsq_ratio.split(':')
            m, f = int(m), int(f)
            if m > f:
                if f == 0:
                    r = u'''<span class="iconm icong">&nbsp;</span><span class="male gender">%s</span>''' % m
                else:
                    r = u'''<span class="iconm icong">&nbsp;</span><span class="male gender">%s</span><em>:</em><span class="iconf icong">&nbsp;</span><span class="female gender">%s</span>''' % (m, f)
            elif m == f:
                r = u'''<span class="iconm icong">&nbsp;</span><span class="male gender">%s</span><em>:</em><span class="iconf icong">&nbsp;</span><span class="female gender">%s</span>''' % (m, f)
            else: # m < f
                if m == 0:
                    r = u'''<span class="iconf icong">&nbsp;</span><span class="female gender">%s</span>''' % f
                else:
                    r = u'''<span class="iconm icong">&nbsp;</span><span class="male gender">%s</span><em>:</em><span class="iconf icong">&nbsp;</span><span class="female gender">%s</span>''' % (m, f)            
        return r
    
    @property
    @attribute_cache('location')
    def location(self):
        city, state = self.city, self.state
        location = 'user-entered'
        if city and state: # match city, state combination
            key = u'%s|%s' % (city.strip().lower(), state.strip().lower())
            location = settings.CITY_STATE_TO_LOCATION_MAP.get(key, 'user-entered')                
        if location == 'user-entered' and state: # match just the state
            location = settings.STATE_TO_LOCATION_MAP.get(state.lower(), 'user-entered')
        return location
       
    def get_current_event(self, include_hidden=False):
        """Return the event happening here now or today. Return None otherwise."""
        today, td = today_timedelta_by_location(self.location)
        q = self.event_set
        if include_hidden:
            q = q.filter(is_approved=True)
        else:
            q = q.active(today=today)            
        events = q.filter(event_date=today).order_by('event_date', 'event_start_time', 'pk')
        for e in events:
            if e.show_checkins:
                return e
        return None


class EventManager(models.Manager):
    def add_is_attending(self, queryset, user_profile):
        """Add is_attending attribute to the given event queryset"""
        return queryset.extra(
            select={
                'is_attending':'''
                select count(*) from %(atab)s
                where %(etab)s.id=%(atab)s.event_id and
                %(atab)s.attendee_profile_id=%(profile_id)s
                ''' % {
                  'atab':Attendee._meta.db_table,
                  'etab':Event._meta.db_table,
                  'profile_id':user_profile.pk
                }
            }
        )

    def active(self, attending_user=None, **kwargs):
        """Return approved events that have not yet ended"""
        today = kwargs.pop('today', None)
        now = today or date.today()
        q = self.visible(is_approved=True, event_date__gte=now, **kwargs)
        if attending_user:
            q = self.add_is_attending(q, user_profile=attending_user)
        return q

    def visible(self, **kwargs):
        """Return events that have not been marked as deleted"""
        return self.select_related('venue', 'creator__user', 'artist').filter(is_deleted=False, **kwargs)

    def public(self, **kwargs):
        """Return True if this event is admin approved and is not deleted i.e. is visible"""
        return self.visible(is_approved=True)

    def active_by_location(self, location=None, attending_user=None, **kwargs):
        """Return active events for the given location"""
        location = location or Event.LOCATION_DEFAULT
        loc_list = [location]
        if location != 'destination':
            loc_list.append('destination')
        return self.active(attending_user=attending_user, **kwargs).filter(location__in=loc_list)

    def active_destination(self, attending_user=None, **kwargs):
        """Return active events that are of global destination"""
        return self.active_by_location(location='destination', attending_user=attending_user, **kwargs)


class VisibleEventManager(models.Manager):
    """A ``Manager`` that includes only those events that have not been marked as deleted."""
    def get_query_set(self, *args, **kwargs):
        return super(VisibleEventManager, self).get_query_set(*args, **kwargs).select_related(
            'venue', 'creator__user'
        ).filter(is_deleted=False)


# Custom image field
class EventImageField(models.ImageField):   
    def generate_filename(self, instance, filename):
        ext = os.path.splitext(filename)[1]
        if not ext:
            ext = '.jpg'
        filename = 'ev-%s-%s-%s-%s%s' % (instance.artist.pk,
                                   instance.pk or uuid4().hex[::6],
                                   slugify(instance.title)[:10],
                                   uuid4().hex[::8],
                                   ext)
        return super(EventImageField, self).generate_filename(instance, filename)

    def save_form_data(self, instance, data):
        """Override default field save action and create resized event images.

        `instance` is a event instance.

        """
        if data and isinstance(data, UploadedFile):
            # A new file is being uploaded. So delete the old one.
            remove_model_image(instance, 'image')
        super(EventImageField, self).save_form_data(instance, data)
        # instance._create_resized_images(raw_field=data, save=False)


class Event(models.Model):
    # Constants --------------------------------------------
    UNLOCK_TYPES = (
        ('audio', 'Audio'),
        ('video', 'Video'),
        ('other', 'Other'),
    )
    LOCATIONS = settings.LOCATIONS
    LOCATION_DEFAULT = settings.LOCATION_DEFAULT
    LOCATIONMAP = settings.LOCATION_MAP
    END_DATE_ARRIVED = 'END_DATE_ARRIVED'
    NUM_ATTENDEES_RECEIVED = 'NUM_ATTENDEES_RECEIVED'
    NO_ATTENDEES_YET = 'NO_ATTENDEES_YET'
    ACTIVE = 'ACTIVE'
    NOT_ACTIVE = 'NOT_ACTIVE'
    TITLE_HELP = _("A title for your event. 120 characters max. For example: Live show!, etc.")
    AUDIO_HELP = _('''An optional embedded widget that plays your tracks. 
        You can create widgets at 
        <a href="http://www.reverbnation.com/" %s>reverbnation.com</a>, 
        <a href="http://www.projectopus.com/" %s>projectopus.com</a> or
        <a href="http://www.imeem.com/" %s>imeem.com</a>
        and paste their code here.''' % (POPUP, POPUP, POPUP))

    # Internal status fields
    is_homepage_worthy = models.BooleanField(_('is homepage worthy'), default=False, db_index=True,
                    help_text=_("Check this box if this event's badge may be picked up for special display on the homepage."))
    homepage_worthy_on = models.DateTimeField(_('homepage worthy on'), 
                    blank=True, null=True, db_index=True,
                    help_text=_("This date and time controls the order in which homepage worthy events are displayed. Chronologically newer ones are displayed first."))
    location = models.CharField(max_length=30, db_index=True, choices=LOCATIONS, default=LOCATION_DEFAULT, 
        help_text=_(u"The city site where this event is displayed."),
    )
    destination_timestamp = models.DateTimeField(_('destination timestamp'), 
                    blank=True, null=True, db_index=True,
                    help_text=_("This date and time controls the order in which destination events are displayed. Chronologically newer ones are displayed first."))
    # Step I:
    title = models.CharField(_('title'), max_length=120, help_text=TITLE_HELP)
    url = models.SlugField(_('URL'), max_length=35, db_index=True, unique=True, blank=True, null=True)
    venue = models.ForeignKey(Venue)
    event_date = models.DateField(_('date'), db_index=True, help_text=_('In the format M/D/YYYY or YYYY-M-D. For example, 7/21/2008 or 2008-7-21.'))
    description = models.TextField(_('description'), help_text=_('A longer description of this event.'), blank=True, null=True)
    # Step III:
    is_free = models.BooleanField(_('Free!'), default=False, db_index=True)
    price_text = models.CharField('price', max_length=250, blank=True, help_text=_(u"Price of entry for this show. For example, \"$25 cover / $20 for students\""))
    ticket_url = models.URLField(_('Ticket URL'), max_length=200, verify_exists=True, db_index=True, null=True, blank=True, help_text=_("The link to this show's ticket purchase web site, if available."))
    hashtag = models.CharField('Twitter comments', max_length=250, blank=True, help_text=_(u"Enter search terms from Twitter, separated by commas and we'll gather the most recent tweets. For example: #coachella, #radiohead, radiohead+coachella"))
    event_start_time = models.TimeField(_('event start time'), db_index=True, blank=True, null=True, help_text=_('Format: 09:00 PM'))
    event_timezone = models.CharField('event timezone', blank=True, max_length=30, default='ET', help_text=_('For example: EST, CST, EDT, ET, Eastern, etc.'))
    mp3_url = models.URLField(_('SoundCloud MP3 URL or embed code'), max_length=200, verify_exists=False, db_index=True, null=True, blank=True,
                              help_text=_('''Enter the direct URL of your SoundCloud.com track or album page and we will embed it in an audio player.
                                  You can also paste in your track's SoundCloud.com embed code here.
                              '''))
    embed_service = models.ForeignKey(OEmbedProvider, null=True, blank=True, help_text=_('These are the embeddable video services we currently support. Select yours.'))
    embed_url = models.URLField(_('external video URL'), max_length=255, null=True, blank=True,
                    help_text=_('''Now paste in the link to your video page and we will generate the 
                                   correct embed code for you. 
                                   <br/>For example: 
                                   <ul style="margin-top:.5em;">
                                       <li>http://vimeo.com/339189</li>
                                       <li>http://www.youtube.com/watch?v=Apadq9iPNxA</li>
                                       <li>http://myspacetv.com/index.cfm?fuseaction=vids.individual&amp;videoid=27687089</li>
                                       <li>http://qik.com/video/3705334</li>
                                       <!-- <li>http://soundcloud.com/asc/asc-the-touch</li> -->
                                   </ul>'''))
    # Step II:
    image = EventImageField(_('event image'), upload_to='badges/original-events/%Y-%b', max_length=250,
                            help_text=_("""We will resize this down for you.
                                <ul>
                                    <li>The image format must be either JPEG or PNG.</li> 
                                    <li>The file size must be under %s MB.</li>
                                </ul>""" % int(settings.EVENT_IMAGE_MAX_SIZE_MB)))
    # Auto-generated image fields:
    image_resized = models.ImageField(_('badge image resized'), upload_to='badges/resized-events/%Y-%b', max_length=250, editable=False) # width_field='resized_width', height_field='resized_height'
    image_square = models.ImageField(_('square image'), upload_to='badges/square-events/%Y-%b', max_length=250, editable=False) # width_field='square_width', height_field='square_height'
    image_square_medium = models.ImageField(_('square medium-sized image'), upload_to='badges/square-medium-events/%Y-%b', max_length=250, editable=False) # width_field='square_medium_width', height_field='square_medium_height'
    image_avatar = models.ImageField(_('avatar sized event image'), upload_to='badges/avatars-events/%Y-%b', max_length=250, editable=False) # width_field='avatar_width', height_field='avatar_height'
    # Image dimensions:
    resized_width = models.PositiveIntegerField(null=True, editable=False)
    resized_height = models.PositiveIntegerField(null=True, editable=False)
    avatar_width = models.PositiveIntegerField(null=True, editable=False)
    avatar_height = models.PositiveIntegerField(null=True, editable=False)
    square_width = models.PositiveIntegerField(null=True, editable=False)
    square_height = models.PositiveIntegerField(null=True, editable=False)
    square_medium_width = models.PositiveIntegerField(null=True, editable=False)
    square_medium_height = models.PositiveIntegerField(null=True, editable=False)
    bg_tile = models.BooleanField(default=True)
    bg_image = EventImageField(_('background image'), upload_to='badges/original-events/bg/%Y-%b', max_length=250, width_field='bg_width', height_field='bg_height',
                               null=True, blank=True,
                               help_text=_("""
                                    <ul>
                                        <li>The image format must be either JPEG or PNG.</li> 
                                        <li>The file size must be under %s MB.</li>
                                    </ul>""" % int(settings.EVENT_BG_IMAGE_MAX_SIZE_MB)))
    bg_width = models.PositiveIntegerField(null=True, editable=False)
    bg_height = models.PositiveIntegerField(null=True, editable=False)
    # Event creator info
    is_member_generated = models.BooleanField(default=False, editable=False)
    creator = models.ForeignKey(UserProfile, null=True, blank=True, editable=True)
    artist = models.ForeignKey(ArtistProfile)
    # Other event fields
    headliner = models.CharField(max_length=200, db_index=True, blank=True)
    artists = models.CharField(max_length=250, db_index=True, blank=True)
    aws_asins = models.CharField(max_length=250, blank=True, help_text=u"Recent Amazon MP3 ASINs (comma-separated) for headlining artist. Used by Amazon MP3 widget.")
    # LastFM fields
    lastfm_id = models.CharField(max_length=50, unique=True, db_index=True, blank=True, null=True, editable=False)
    lastfm_venue_url = models.URLField(max_length=200, verify_exists=False, db_index=True, blank=True, default='', editable=False)
    # Statistics
    tweet_count = models.PositiveIntegerField(default=0, db_index=True)
    comment_count = models.PositiveIntegerField(default=0, db_index=True)
    # Unused fields
    price = models.DecimalField(_('price ($)'), max_digits=10, decimal_places=2, blank=True, editable=False, help_text=_('What is the price of entry (in US dollars)? Enter 0, if the event is free.'))
    max_attendees = models.PositiveIntegerField(_('maximum number of attendees'), editable=False, blank=True, help_text=_("What's the maximum number of attendees allowed for this event? Leave empty if there's no limit."))
    min_age = models.PositiveSmallIntegerField(_('attendee minimum age'), blank=True, editable=False, help_text=_("Minimum age in years for a person to be eligible to attend this event. Leave empty if there's no age restriction. If you fill in this field, attendees will be prompted to enter their age."))
    fan_note = models.TextField(_('Thank you note'), blank=True, null=True, editable=False, help_text=_('An optional plain-text message to be included in the email that is sent out to fans when they register to attend this event.'))
    event_end_time = models.TimeField(_('event end time'), blank=True, null=True, editable=False, help_text=_('In the format HH:mm. For example, if you want 9:30pm, type in 21:30'))
    audio_player_embed = models.TextField(_('Embed audio player'), editable=False, blank=True, null=True, max_length=2000, help_text=AUDIO_HELP)
    # admin fields
    ext_event_id = models.CharField(max_length=50, db_index=True, blank=True, editable=False, default=u'')
    ext_event_source = models.CharField(max_length=50, db_index=True, blank=True, editable=False, default=u'')
    has_image = models.BooleanField(default=True, db_index=True, editable=False)
    max_tweets = models.PositiveIntegerField(default=0, null=True, blank=True, help_text=u"Leave empty to use default. Max is 1000.")
    uuid = models.CharField(max_length=40, db_index=True, blank=True, editable=False)
    tm_url = models.CharField('TicketMaster URL', max_length=750, blank=True, db_index=True, help_text=u"Auto-generated TicketMaster URL. Don't modify this. Instead, update the Ticket URL above.")
    is_submitted = models.BooleanField(_('is submitted'), default=False, db_index=True,
                    help_text=_('When this is checked, it means that the artist has submitted this event for approval.'))
    submitted_on = models.DateTimeField(_('submitted on'), blank=True, null=True)
    is_approved = models.BooleanField(_('is approved'), default=False, db_index=True,
                    help_text=_('Check this box to approve and activate this event.'))
    approved_on = models.DateTimeField(_('approved on'), blank=True, null=True)
    special_badge_text = models.CharField(_('badge text'), blank=True, max_length=50, editable=False, help_text=_("Special badge text. For example: SPONSORED! Please keep it a short single word."))
    is_deleted = models.BooleanField(_('is hidden'), default=False, db_index=True,
                    help_text=_('When this is checked, this event will be visible only in the admin area and nowhere else.'))
    edited_on = models.DateTimeField(_('edited on'), blank=True, null=True)
    # unlock-related fields:
    has_unlock = models.BooleanField(default=False, db_index=True)
    unlock_subject = models.CharField(max_length=50, blank=True, default=u'')
    unlock_body = models.TextField(null=True, blank=True, default=u'')
    unlock_type = models.CharField(max_length=25, blank=True, default=u'', choices=UNLOCK_TYPES)    
    unlock_link = models.CharField(max_length=200, blank=True, default=u'')    

    objects = EventManager()
    visible_objects = VisibleEventManager()

    class Meta:
        ordering = ('-event_date',)
        permissions = (("can_manage_events", "Can manage events"),)

    def __unicode__(self):
        return u'%s: %s' % (self.artist.name, self.title)

    def get_absolute_url(self, force_hostname=False):
        if self.url:
            _url = reverse('view_event_seo', kwargs={'event_url':self.url, 'artist_url':self.artist.url})
        else:
            _url = reverse('view_event', kwargs={'event_id':self.pk})
        # if settings.DEV_MODE and not force_hostname:
        #    return _url
        return u'http://%s%s%s' % (self.subdomain, _SUBDOMAIN_PORT, _url)

    def save(self, **kwargs):
        just_approved, just_deleted = False, False
        is_update = self.pk is not None
        hashtags_changed = False
        if is_update and (self.is_approved or self.is_deleted):
            # Check if this event was just approved/deleted
            # based on its status in the DB's old copy.
            db_copy = Event.objects.get(pk=self.pk)
            just_approved = self.is_approved and not db_copy.is_approved
            just_deleted = self.is_deleted and not db_copy.is_deleted
            # Check if hashtags have changed
            hashtags_changed = set(db_copy.hashtags) != set(self.hashtags)
        if self.max_tweets and self.max_tweets > 1000:
            self.max_tweets = 1000
        if not self.price:
            self.price = 0
        if not self.min_age:
            self.min_age = 0
        if not self.max_attendees:
            self.max_attendees  = 0
        if self.mp3_url:
            self.audio_player_embed = u''
        if self.audio_player_embed:
            self.mp3_url = u''
        if self.is_submitted and not self.submitted_on:
            self.submitted_on = datetime.now()
        if self.is_approved and not self.approved_on:
            self.approved_on = datetime.now()
        if self.is_homepage_worthy and not self.homepage_worthy_on:
            self.homepage_worthy_on = datetime.now()
        if self.description:
            self.description = self.description.replace('\r\n', '\n')
        if self.fan_note:
            self.fan_note = self.fan_note.replace('\r\n', '\n')
        if not self.event_start_time:
            self.event_timezone = u''
        elif not self.event_timezone:
            self.event_timezone = u''
        self.event_end_time = self.event_start_time
        self.is_member_generated = (self.artist.url == 'riotvine-member')
        if self.location == 'user-entered' or getattr(self, '_venue_changed', False):
            # merge into a supported location if states or cities match
            city, state = self.venue.city, self.venue.state
            if city and state: # match city, state combination
                key = u'%s|%s' % (city.strip().lower(), state.strip().lower())
                self.location = settings.CITY_STATE_TO_LOCATION_MAP.get(key, 'user-entered')                
            if self.location == 'user-entered' and state: # match just the state
                self.location = settings.STATE_TO_LOCATION_MAP.get(state.lower(), 'user-entered')
        self.set_artist_names()
        self.tm_url = u''
        self.set_tm_url()
        self.set_aws_asins()
        if not self.uuid:
            self.uuid = uuid4().hex
        super(Event, self).save(**kwargs)
        if not is_update: # When an Event is first created, create an empty Stats child object for it.
            Stats.objects.get_or_create(event=self)
        # ActionItem.objects.q_event_action(self, 'generate-badges')
        self.create_badges()
        # ActionItem.objects.q_event_action_done(self, 'generate-badges')
        if just_approved:
            # ActionItem.objects.q_admin_action_done(self, 'approve-event')
            # ActionItem.objects.q_event_action(self, 'email-event-approval')
            event_signals.post_event_approval.send(sender=self.__class__, instance=self)
        if just_deleted:
            # ActionItem.objects.q_admin_action_done(self, 'delete-event')
            event_signals.post_event_deletion.send(sender=self.__class__, instance=self)
        self.get_short_url() # invoke bitly shortener
        if not is_update or (is_update and hashtags_changed):
            if is_update and hashtags_changed and not quote_hashtags(self.hashtags):
                # hashtags have been deleted
                self.eventtweet_set.delete_tweets_for_event(event=self)
                self.tweet_count = self.eventtweet_set.count()
                super(Event, self).save(**kwargs)
                _log.warn("Reset tweets for event %s\n%s", self.pk, self.title)
                hashtags_changed = False # avoid another reset
            tasks.fetch_event_tweets(event=self, do_reset=hashtags_changed, high_priority=(not self.is_auto_generated))

    def delete(self):
        # ActionItem.objects.q_admin_action_done(self, 'delete-event')
        super(Event, self).delete()

    @attribute_cache('get_short_url')
    def get_short_url(self):
        u = self.get_absolute_url()
        if settings.DEV_MODE and not u.startswith('http'):
            url = u"http://%s%s" % (self.subdomain, self.get_absolute_url())
            return get_tiny_url(url)
        return get_tiny_url(u)
    
    def get_short_url_for_sharer(self, sharer_id, shorten=True):
        _url = reverse('view_shared_event', kwargs={'event_id':self.pk, 'sharer_id':sharer_id})
        u = u'http://%s%s%s' % (self.subdomain, _SUBDOMAIN_PORT, _url)
        return shorten and get_tiny_url(u) or u
    
    def get_full_url_for_sharer(self, sharer_id):
        return self.get_short_url_for_sharer(sharer_id, shorten=False)

    @property
    @attribute_cache('subdomain')
    def subdomain(self):
        if settings.DEV_MODE:
            return settings.DEV_SITE_DOMAIN
        if self.location == 'destination':
            return settings.DISPLAY_SITE_DOMAIN
        sub = settings.LOCATION_SUBDOMAIN_REVERSE_MAP.get(self.location, 'www')
        if sub and sub.lower() == 'www':
            sub = ""
        else:
            sub = "%s." % sub
        return u"%s%s" % (sub, settings.DISPLAY_SITE_DOMAIN)

    @attribute_cache('get_short_url_or_none')
    def get_short_url_or_none(self):
        u = self.get_short_url()
        if u and len(u) < 25:
            return u
        return None

    @property
    def display_price_text(self):
        if self.is_free and not self.price_text:
            return u'Free!'
        else:
            return self.price_text
        
    @property
    def has_start_time(self):
        return self.event_start_time is not None
    
    @property
    def has_end_time(self):
        return self.event_end_time is not None

    def set_tm_url(self, save=False):
        """Set TicketMaster URL. Return True if set. False otherwise."""
        if self.is_auto_generated and not self.is_free:
            # generate TicketMaster URL
            if not self.ticket_url:
                from event.utils import get_ticketmaster_search_url
                qlist = [self.headliner or self.title, self.venue.alias_or_name, self.venue.city, self.venue.state]
                qlist = [q.encode("utf-8") for q in qlist]
                querystring = ' '.join(qlist)
                search_url = get_ticketmaster_search_url(querystring)
                if search_url:
                    # search succeeded; save URL
                    self.tm_url = search_url
                    if save:
                        super(Event, self).save()
                    return True
        if save:
            super(Event, self).save()
        return False

    def set_aws_asins(self, save=False, force=False):
        """Set Amazon ECS ASINs for headliner of this event. Return True if set. False otherwise."""
        if self.is_auto_generated and not self.aws_asins:
            if not self.headliner:
                if not self.set_artist_names(): # extract artist names from description
                    return False
            if self.headliner:
                from artist.utils import get_asins
                asins = get_asins(self.headliner.encode("utf-8"), force=force)
                if asins:
                    self.aws_asins = ",".join(asins)[:250]
                    if save:
                        super(Event, self).save()
                    return True
        return False

    @property
    def sort_date(self):
        """Date field used to merge campaigns and events together into a mixed feed."""
        return self.event_date

    def _create_resized_images(self, raw_field, save):
        """Generate scaled down images needed for event badges and avatars."""
        if not self.image:
            return None
        # Derive base filename (strip out the relative directory).
        filename = os.path.split(self.image.name)[-1]
        ctype = guess_type(filename)[0]
        ext = os.path.splitext(filename)[1]
        if not ext:
            ext = '.jpg'

        t = None
        try:
            try:
                pth = self.image.path
            except NotImplementedError:
                from django.core.files.temp import NamedTemporaryFile
                t = NamedTemporaryFile(suffix=ext)
                ix = self.image
                from boto.exception import S3ResponseError
                try:
                    for d in ix.chunks(4000000):
                        t.write(d)
                except S3ResponseError:
                    # on S3 errors, stop further processing of images
                    t.close()
                    return
                t.flush()
                t.seek(0)
                pth = t

            # Generate resized copy of image.
            # resize, crop, img = get_perfect_fit_resize_crop(settings.EVENT_RESIZED_IMAGE_BOUNDING_BOX, input_image=self.image.path)
            # resized_contents = resize_in_memory(img, resize, crop=crop)
            resized_contents = resize_in_memory(pth, settings.EVENT_RESIZED_IMAGE_BOUNDING_BOX, crop=None, crop_before_resize=False, restrict_width=True)
            if resized_contents:
                remove_model_image(self, 'image_resized')
                self.image_resized = None
                resized_file = str_to_file(resized_contents)
                resized_field = InMemoryUploadedFile(resized_file, None, None, ctype, len(resized_contents), None)
                self.image_resized.save(name='resized-%s' % filename, content=resized_field, save=save)
                resized_file.close()

            # Generate avatar.            
            if t:
                t.seek(0)
            avatar_contents = resize_in_memory(pth, settings.EVENT_AVATAR_IMAGE_CROP, crop=settings.EVENT_AVATAR_IMAGE_CROP, crop_before_resize=True)
            if avatar_contents:
                remove_model_image(self, 'image_avatar')
                self.image_avatar = None
                avatar_file = str_to_file(avatar_contents)
                avatar_field = InMemoryUploadedFile(avatar_file, None, None, ctype, len(avatar_contents), None)
                self.image_avatar.save(name='avatar-%s' % filename, content=avatar_field, save=save)
                avatar_file.close()

            # Generate square image.            
            if t:
                t.seek(0)
            avatar_contents = resize_in_memory(pth, settings.EVENT_AVATAR_IMAGE_SQUARE_CROP, crop=settings.EVENT_AVATAR_IMAGE_SQUARE_CROP, crop_before_resize=True)
            if avatar_contents:
                remove_model_image(self, 'image_square')
                self.image_square = None
                avatar_file = str_to_file(avatar_contents)
                avatar_field = InMemoryUploadedFile(avatar_file, None, None, ctype, len(avatar_contents), None)
                self.image_square.save(name='sq-%s' % filename, content=avatar_field, save=save)
                avatar_file.close()

            # Generate medium-sized square image.            
            if t:
                t.seek(0)
            avatar_contents = resize_in_memory(pth, settings.EVENT_AVATAR_IMAGE_SQUARE_MEDIUM_CROP, crop=settings.EVENT_AVATAR_IMAGE_SQUARE_MEDIUM_CROP, crop_before_resize=True)
            if avatar_contents:
                remove_model_image(self, 'image_square_medium')
                self.image_square_medium = None
                avatar_file = str_to_file(avatar_contents)
                avatar_field = InMemoryUploadedFile(avatar_file, None, None, ctype, len(avatar_contents), None)
                self.image_square_medium.save(name='sq-med-%s' % filename, content=avatar_field, save=save)
                avatar_file.close()

            if t:
                t.close()
            if save:
                super(Event, self).save()
        except Exception:
            raise
        finally:
            if t:
                t.close()

    def admin_artist_link(self):
        return admin_url(self.artist, verbose_name=self.artist.short_name)
    admin_artist_link.short_description = 'artist'
    admin_artist_link.allow_tags = True
    admin_artist_link.admin_order_field = 'artist'

    def admin_stats_link(self):
        return admin_url(self.stats, verbose_name=(self.target_amount or 'free!'))
    admin_stats_link.short_description = 'target'
    admin_stats_link.allow_tags = True
    admin_stats_link.admin_order_field = 'target_amount'

    def admin_max_attendees(self):
        return self.max_attendees
    admin_max_attendees.short_description = 'max attendees'
    admin_max_attendees.admin_order_field = 'max_attendees'

    def admin_status(self):
        if self.is_deleted:
            return u'Hidden'
        if self.is_submitted and not self.is_approved:
            return u'Submitted'
        if self.is_approved:
            if self.is_homepage_worthy:
                return u'Homepage worthy'
            else:
                return u'Approved'
        if self.is_payout_requested:
            return u'Payout requested'
    admin_status.short_description = 'status'
    
    @property
    @attribute_cache('whos_here')
    def whos_here(self):
        # get 4sq checkin faces
        key = shorten_key(u"venue_4sq:%s" % self.venue.pk)
        return cache.cache.get(key, [])

    def get_gcal_params(self):
        """Return a Google Calendar formatted dictionary.

        action=TEMPLATE&
        text=RV%20Event&
        dates=20100105T220000/20100105T220200&
        details=My%20Description.%0D%0ALine%20%232&
        location=My%20Location%2C%20Street%2C%20City%2C%20Zip&
        trp=false&
        sprop=http%3A%2F%2Friotvine.com&
        sprop=name:RiotVine

        Date format is: dt.strftime("%Y%m%dT%H%M00")

        """
        gcal = {'action':'TEMPLATE', 'trp':'false'}
        gcal['text'] = self.title
        gcal['sprop'] = u"website:http://%s" % settings.DISPLAY_SITE_DOMAIN
        url = self.get_short_url()
        desc = u'See more details at RiotVine:\n\n%s\n' % url
        # if self.venue.map_url:
        #    vurl = self.venue.map_url
        #    desc = desc + u'\n\nLocation Map: %s\n' % vurl
        gcal['details'] = desc
        location = self.venue.name + ' - ' + self.venue.address + ' - ' + self.venue.citystatezip
        gcal['location'] = location
        d, t = self.event_date, self.event_start_time
        if t:
            start = datetime(d.year, d.month, d.day, t.hour, t.minute)
        else:
            start = datetime(d.year, d.month, d.day)
        gcal_start = start.strftime("%Y%m%dT%H%M00")
        gcal_end = gcal_start
        gcal['dates'] = u"%s/%s" % (gcal_start, gcal_end)
        return gcal
    
    @property
    def mp3_embed_service(self):
        if self.mp3_url and 'soundcloud.com' in self.mp3_url:
            return OEmbedProvider.objects.get(host__iexact='soundcloud.com', service_type='rich')
        else:
            return None

    @property
    def ticket_or_tm_url(self):
        return self.ticket_url or self.tm_url
    
    @property
    def image_square_medium_url(self):
        try:
            return self.image_square_medium.url
        except:
            return ""
        
    @property
    def image_square_url(self):
        try:
            return self.image_square.url
        except:
            return ""
        
    @property
    def image_resized_url(self):
        try:
            return self.image_resized.url
        except:
            return ""
        
    @property
    def image_avatar_url(self):
        try:
            return self.image_avatar.url
        except:
            return ""

    def set_artist_names(self):
        """Extract headliner and other artist names from event description and 
        populate them for this instance.
        <ul class='artist_list'>
            <li>headliner</li>
            <li>artist 2</li>
            <li>artist 3</li>
        </ul>
        """
        if self.headliner or self.artists:
            return False # don't do anything if fields are already populated
        if "<ul class='artist_list'>" in self.description[:400]:
            soup = BeautifulSoup(self.description)
            ul = soup.findAll('ul', attrs={'class':'artist_list'})
            artists = []
            if ul:
                for li in ul[0].findChildren():
                    name = li.string
                    if name:
                        artists.append(name)
            if artists:
                self.headliner = artists[0][:200]
                self.artists = u",".join(artists)[:250]
                return True
        return False # artist names not found


    @property
    @attribute_cache('owner')
    def owner(self):
        if self.creator:
            return self.creator.user
        return self.artist.user_profile.user
    
    @property
    @attribute_cache('owner_profile')
    def owner_profile(self):
        if self.creator:
            return self.creator
        return self.artist.user_profile

    @property
    def is_auto_generated(self):
        """Return True if this event was generated by riotvine-member i.e. auto-generated"""
        return bool(self.ext_event_source) or self.owner.username == 'riotvine_member' 
    
    @property
    def show_creator(self):
        return self.creator.username != 'riotvine_member'
    
    def get_interested(self, limit=500, order_by="-added_on"):
        """Utility function to get users interested in an event"""
        e = self
        interested = e.attendee_set.active().select_related('attendee_profile__user').order_by(order_by)
        if limit:
            interested = interested[:int(limit)]
        ix = set()
        interested_list = []
        for ii in interested: # remove dupes
            if ii.attendee_profile.pk not in ix:
                interested_list.append(ii)
                ix.add(ii.attendee_profile.pk)
        return interested_list

    @property
    @attribute_cache('attendeeset')
    def attendeeset(self):
        """Return a set of user_profile ids of this user's friends"""
        key = u"attendeeset:%s" % key_suffix('attendees', self.pk)
        key = short_key(key)
        value = cache.cache.get(key, None)
        if value is None:
            value = set(self.attendee_set.active().values_list('attendee_profile_id', flat=True))
            cache.cache.set(key, value, 3600*12)
        return value

    def is_user_qualified(self, user):
        """Return tuple (True/False, reason_list) based on whether user abides by all 
        event rules or not.

        Return True if user qualifies. False, otherwise. When False, return a list of 
        reasons for non-qualification.

        """
        reason_list = []
        qual = True
        p = user.get_profile()
        if self.min_age:
            if p.age is None:
                qual = False
                reason_list.append('NO_BIRTH_DATE')
            elif p.age < self.min_age:
                qual = False
                reason_list.append('NOT_OLD_ENOUGH')
        return (qual, reason_list)

    @property
    @attribute_cache('is_editable')
    def is_editable(self):
        if self.is_deleted or self.has_ended:
            return False
        if self.changed_version and self.changed_version.is_approved:
            # Allow queue processor to merge approved changes before permitting new edits.
            return False
        return True

    @property
    @attribute_cache('is_public')
    def is_public(self):
        return not self.is_deleted and self.is_approved

    @property
    @attribute_cache('is_active')
    def is_active(self):
        today, td = today_timedelta_by_location(self.location, self.event_timezone)
        return not self.is_deleted and self.is_approved and self.event_date >= today
    
    @property
    @attribute_cache('timedelta')
    def timedelta(self):
        """Return timedelta relative to Eastern timezone"""
        today, td = today_timedelta_by_location(self.location, self.event_timezone)
        return td
    
    @property
    @attribute_cache('is_today')
    def is_today(self):
        today, td = today_timedelta_by_location(self.location, self.event_timezone)
        return self.event_date == today
    
    @property
    @attribute_cache('show_checkins')
    def show_checkins(self):
        '''Return True if checkins should now be shown for this event based on the current time.
        
        If event has no start time, show checkins all day long.
        If event has start time, show checkins if start time has already elapsed or start time is less than 1 hour from now.
        '''                
        today, td = today_timedelta_by_location(self.location, self.event_timezone)
        if self.event_date != today:
            return False
        if not self.event_start_time:
            return True
        now = td and (datetime.now() - td) or datetime.now()
        threshold = now + timedelta(minutes=settings.CHECKIN_THRESHOLD_MINUTES) # 80 mins from now
        dt = self.event_date
        t = self.event_start_time
        et = datetime(dt.year, dt.month, dt.day, t.hour, t.minute) 
        return et <= threshold # event time is less than one hour from now or time has elapsed

    @property
    @attribute_cache('has_ended')
    def has_ended(self):
        today, td = today_timedelta_by_location(self.location, self.event_timezone)
        return self.is_approved and self.event_date < today

    @property
    @attribute_cache('has_photos')
    def has_photos(self):
        return Photo.objects.get_for_object(self).count()

    @property
    @attribute_cache('is_deletable')
    def is_deletable(self):
        """Return true if this event has not been approved or has not yet started AND
        no attendees are associated with it.

        In all other cases, an admin needs to review the event before it may be deleted.

        """
        # For now, delete requests are emailed to the admin.
        return False

    @property
    @attribute_cache('hashtags')
    def hashtags(self):
        """Return list of hashtags"""
        if self.hashtag:
            return self.hashtag.split(",")
        else:
            return []

    def image_preview(self):
        """Return HTML fragment to display event image."""
        h = '<img src="%s" alt="%s"/>' % (self.image_resized_url, self.title)
        return mark_safe(h)
    image_preview.allow_tags = True
    image_preview.short_description = 'image'

    def avatar_preview(self):
        """Return HTML fragment to display event avatar."""
        h = '<img src="%s" alt="%s"/>' % (self.image_avatar_url, self.title)
        return mark_safe(h)
    avatar_preview.allow_tags = True
    avatar_preview.short_description = 'avatar'

    @property
    @attribute_cache('short_title')
    def short_title(self):
        """Return a short title for the event."""
        return truncate_words(self.title, settings.EVENT_SHORT_TITLE_WORDS)

    @property
    @attribute_cache('title_with_tinyurl')
    def title_with_tinyurl(self):
        """Return event suffixed with the bit.ly URL"""
        #if self.lastfm_id and not "http://" in self.title:
        #    u = self.get_short_url_or_none()
        #    if u:
        #        return u"%s %s" % (self.title, u)
        return self.title

    @property
    @attribute_cache('short_name_for_twitter')
    def short_name_for_twitter(self):
        n = len(self.title)
        if n <= settings.TWITTER_EVENT_NAME_MAX_LENGTH:
            return self.title
        else:
            return u"%s..." % self.title[:settings.TWITTER_EVENT_NAME_MAX_LENGTH-3]

    @property
    @attribute_cache('is_complete')
    def is_complete(self):
        """Return (True/False, reason) if this event is complete, based on any of these rules:
          - End date has arrived
          - Total number of attendees has been met
          See ``completion_status`` below.

        """
        completed, reason = self.completion_status
        return completed

    @property
    @attribute_cache('action_name')
    def action_name(self):
        return 'add to my shows'

    @property
    @attribute_cache('completion_status')
    def completion_status(self):
        """Return a tuple with event_completion_status and completion reason."""
        today, td = today_timedelta_by_location(self.location, self.event_timezone)
        if self.event_date < today:
            return True, self.END_DATE_ARRIVED
        try:
            if self.max_attendees and (self.stats.num_attendees == self.max_attendees):
                return True, self.NUM_ATTENDEES_RECEIVED
        except Stats.DoesNotExist:
            return False, self.NO_ATTENDEES_YET
        return False, self.is_active and self.ACTIVE or self.NOT_ACTIVE

    @property
    @attribute_cache('is_sold_out')
    def is_sold_out(self):
        if self.max_attendees:
            return self.num_attendees == self.max_attendees
        else:
            return False

    @property
    @attribute_cache('stats')
    def stats(self):
        try:
            return self.stats_set.get()
        except Stats.DoesNotExist:
            return self.stats_set.create()

    def num_left_for_user(self, user):
        """Return number of registration slots left for ``user``."""
        q = self.attendee_set.filter(attendee=user)
        num_user = sum([c.qty for c in q])
        remaining = 1 - num_user
        if remaining < 0:
            remaining = 0
        return remaining

    @property
    @attribute_cache('num_attendees_left')
    def num_attendees_left(self):
        """Return the number of attendee slots left."""
        if self.is_complete:
            return 0
        attendees_left = self.max_attendees - self.stats.num_attendees
        if attendees_left < 0:
            attendees_left = 0
        return attendees_left

    @property
    @attribute_cache('num_attendees')
    def num_attendees(self):
        """Return number of attendees for this event."""
        return self.stats.num_attendees

    @property
    @attribute_cache('interested_count')
    def interested_count(self):
        return len(self.attendeeset)
    num_interested = interested_count

    @property
    @attribute_cache('short_title_chars')
    def short_title_chars(self):
        """Return the event's title upto ``settings.EVENT_SHORT_TITLE_LENGTH`` characters long."""
        if len(self.title) > settings.EVENT_SHORT_TITLE_LENGTH:
            return mark_safe(u'%s&hellip;' % self.title[:settings.EVENT_SHORT_TITLE_LENGTH])
        else:
            return self.title

    def _badge_chars_per_line(self, text, font, font_size):
        """Return characters per line computed to fit within a badge's available area."""
        xmin, y = settings.EVENT_BADGE_TITLE_POSITION
        xmax, y = settings.EVENT_BADGE_CALLOUT_POSITION
        width_available = xmax - xmin - settings.EVENT_BADGE_TITLE_CLEARANCE # clearance
        font = ImageFont.truetype(font, font_size, encoding='unic')
        w, h = font.getsize(text)
        pixels_per_char = float(w)/float(len(text))
        chars_per_line = int(width_available/pixels_per_char)
        # If chars_per_line is slightly off, adjust it
        one_line = text[:chars_per_line]
        w, h = font.getsize(one_line)
        dw = w - width_available
        if dw > 0:
            dchar = dw/pixels_per_char + 2
            chars_per_line -= dchar
        return chars_per_line

    @property
    @attribute_cache('artist_short_name_for_badge')
    def artist_short_name_for_badge(self):
        name = self.artist.name
        chars_per_line = self._badge_chars_per_line(self.artist.name, settings.EVENT_BADGE_ARTIST_FONT, settings.EVENT_BADGE_ARTIST_FONT_SIZE)
        if len(name) > chars_per_line:
            return u'%s...' % name[:chars_per_line]
        else:
            return name

    @property
    @attribute_cache('short_title_wrapped_for_badge')
    def short_title_wrapped_for_badge(self):
        """Return the event's title with wrapped lines to fit a badge.

        Each line is returned as a list element.

        """
        chars_per_line = self._badge_chars_per_line(self.title, settings.EVENT_BADGE_TITLE_FONT, settings.EVENT_BADGE_TITLE_FONT_SIZE)
        max_lines = settings.EVENT_BADGE_TITLE_MAX_LINES
        if len(self.title) > chars_per_line:
            wrapped = textwrap.wrap(self.title, chars_per_line)
            ellipsis_needed = len(wrapped) > max_lines
            wrapped = wrapped[:max_lines]
            if ellipsis_needed or len(wrapped[max_lines - 1]) > chars_per_line:
                wrapped[max_lines - 1] = u'%s...' % wrapped[max_lines - 1][:-3]
            return wrapped
        else:
            return [self.title]

    def create_badges(self, badge_types=None):
        return # Badge creation disabled
        if badge_types is None:
            badge_types = map(lambda x:x[0], Badge.BADGE_TYPES)
        for t in badge_types:
            try:
                badge = self.badge_set.get(badge_type=t)
            except Badge.DoesNotExist:
                badge = Badge(event=self, badge_type=t)
            self.create_badge(badge)

    def create_badge(self, badge, special=None, num_attendees=None):
        badgegen.create_badge(event=self, badge=badge, special=special, num_attendees=num_attendees)

    def recompute(self):
        """Recompute event statistics."""
        stats, created = Stats.objects.get_or_create(event=self)
        # Stats from attendees:
        q = Attendee.objects.active().filter(event=self)
        stats.num_attendees = q.count()
        stats.save()
        # queue up an action to generate/update badges
        # ActionItem.objects.q_event_action(self, 'generate-badges')

    @property
    @attribute_cache('changed_version')
    def changed_version(self):
        """Return the latest unapproved changes for this event."""
        try:
            return EventChange.objects.get(event__pk=self.pk)
        except EventChange.DoesNotExist:
            return None

    def notify_attendees(self, message, exclude=None):
        exclude = exclude or []
        for a in self.attendee_set.select_related('attendee').all():
            if a.attendee.pk not in exclude:
                a.attendee.specialmessage_set.create(message=message)


class EventChange(models.Model):
    """A model to hold unapproved edits to an active event listing."""
    MERGE_FIELDS = (
        'title',
        'max_attendees',
        'price',
        'description',
        'venue',
        'zip_code',
        'event_date',
        'event_start_time', 
        'event_end_time',
        'event_timezone',
        'fan_note',
        'audio_player_embed',
        'mp3_url',
        'embed_service',
        'embed_url', 
    )
    BOOLEAN_MERGE_FIELDS = ()
    event = models.ForeignKey(Event, unique=True)
    title = models.CharField(_('event title'),
                                blank=True, null=True,
                                max_length=120,
                                help_text=Event.TITLE_HELP)
    description = models.TextField(_('description'),
                                blank=True, null=True,
                                help_text=_('A longer description of this event.'))
    price = models.DecimalField(_('price ($)'),
                                max_digits=10,
                                decimal_places=2,
                                blank=True, null=True,
                                help_text=_('What is the price of entry (in US dollars)? Enter 0, if the event is free.'))
    venue = models.CharField(_('event venue'),
                                max_length=255,
                                blank=True, null=True,
                                help_text=_('The location of this event without the zip code. For example: Xaviers Cafe, 123 Street, Cambridge, MA'))
    event_date = models.DateField(_('event date'), blank=True, null=True, help_text=_('In the format M/D/YYYY or YYYY-M-D. For example, 7/21/2008 or 2008-7-21.'))
    event_start_time = models.TimeField(_('event start time'), blank=True, null=True, help_text=_('In the format HH:mm. For example, if you want 9 pm, type in 21:00'))
    event_end_time = models.TimeField(_('event end time'), blank=True, null=True, editable=False, help_text=_('In the format HH:mm. For example, if you want 9:30pm, type in 21:30'))
    event_timezone = models.CharField('event timezone', blank=True, null=True, max_length=20, default='ET', help_text=_('For example: EST, CST, EDT, ET, Eastern, etc.'))
    max_attendees = models.PositiveIntegerField(_('maximum number of attendees'),
                                blank=True, null=True,
                                help_text=_("What's the maximum number of attendees allowed for this event? Leave empty if there's no limit."))
    min_age = models.PositiveSmallIntegerField(_('attendee minimum age'),
                        blank=True, null=True,
                        help_text=_("Minimum age in years for a person to be eligible to attend this event. Leave empty if there's no age restriction."))
    fan_note = models.TextField(_('Thank you note'), blank=True, null=True, editable=False,
                                help_text=_('An optional plain-text message to be included in the email that is sent out to fans when they register to attend this event.'))
    audio_player_embed = models.TextField(_('Embed audio player'), blank=True, null=True, max_length=2000, help_text=Event.AUDIO_HELP)
    mp3_url = models.URLField(_('Direct MP3 URL'), max_length=200, verify_exists=_MP3_URL_VERIFY_EXISTS,
        db_index=True, null=True, blank=True, help_text=_('Enter the direct URL of your hosted MP3 file and we will embed it in an audio player.'))
    embed_service = models.ForeignKey(OEmbedProvider, null=True, blank=True,
                    help_text=_('These are the embeddable video services we currently support. Select yours.'))
    embed_url = models.URLField(_('external video url'), max_length=255, null=True, blank=True,
                    help_text=_('''Now paste in the link to your video page and we will generate the 
                                   correct embed code for you. 
                                   For example: 
                                   <ul>
                                       <li>http://vimeo.com/339189</li>
                                       <li>http://www.youtube.com/watch?v=Apadq9iPNxA</li>
                                       <li>http://myspacetv.com/index.cfm?fuseaction=vids.individual&amp;videoid=27687089</li>
                                   </ul>'''))
    is_submitted = models.BooleanField(_('is submitted'), default=False, db_index=True, editable=False,
                    help_text=_('When this is checked, it means that the artist has submitted this change for approval.'))
    submitted_on = models.DateTimeField(_('submitted on'), blank=True, null=True, editable=False)
    added_on = models.DateTimeField(_('added on'), blank=True, null=True, db_index=True)
    edited_on = models.DateTimeField(_('last edited on'), blank=True, null=True)
    is_approved = models.BooleanField(_('is approved'), default=False, db_index=True,
                    help_text=_('Check this box to approve and activate this change. This action can not be undone.'))

    def __unicode__(self):
        return unicode(self.event)

    class Meta:
        ordering = ('-event_date',)

    def save(self, *args, **kwargs):
        if not self.added_on:
            self.added_on = datetime.now()
        if not self.is_approved:
            self.edited_on = datetime.now()
            self.is_submitted = True
            self.submitted_on = datetime.now()
        just_approved = False
        is_update = self.pk is not None
        if self.mp3_url:
            self.audio_player_embed = u''
        if self.audio_player_embed:
            self.mp3_url = u''
        if self.description:
            self.description = self.description.replace('\r\n', '\n')
        if self.fan_note:
            self.fan_note = self.fan_note.replace('\r\n', '\n')
        self.event_end_time = self.event_start_time
        if is_update and self.is_approved:
            # Check if this change was just approved
            # based on its status in the DB's old copy.
            db_copy = EventChange.objects.get(pk=self.pk)
            just_approved = self.is_approved and not db_copy.is_approved
        # Clear out fields that were not changed
        n_changes = 0
        for fname in self.MERGE_FIELDS:
            ch = getattr(self, fname)
            if ch:
                if ch == getattr(self.event, fname):
                    setattr(self, fname, None)
                else:
                    n_changes += 1
        if not self.zip_code:
            self.zip_code = u''
        super(EventChange, self).save(*args, **kwargs)
        if just_approved:
            # ActionItem.objects.q_admin_action_done(self.event, 'approve-event-edit')
            # ActionItem.objects.q_event_action(self.event, 'merge-event-edits')
            pass

    def delete(self):
        # ActionItem.objects.q_event_action_done(self.event, 'merge-event-edits')
        # ActionItem.objects.q_admin_action_done(self.event, 'approve-event-edit')
        super(EventChange, self).delete()

    @property
    @attribute_cache('embed_service_latest')
    def embed_service_latest(self):
        """Return embed_service from this instance or from the event instance."""
        return self.embed_service and self.embed_service or self.event.embed_service


class Badge(models.Model):
    """Model for internal/external badges for an event."""
    BADGE_TYPES = (('i', 'Internal'), ('e', 'External'))
    BADGE_BG_IMAGES = {'i':_BADGE_BG_IMAGE_INTERNAL, 'e':_BADGE_BG_IMAGE_EXTERNAL}

    event = models.ForeignKey(Event)
    badge_type = models.CharField(max_length=1, db_index=True, choices=BADGE_TYPES)
    image = models.ImageField(upload_to='badges/generated-events/%Y-%b', max_length=250, editable=False,
                              width_field='image_width',
                              height_field='image_height')
    image_width = models.PositiveIntegerField(_('width'), null=True, editable=False)
    image_height = models.PositiveIntegerField(_('height'), null=True, editable=False)
    updated_on = models.DateTimeField(blank=True)

    class Meta:
        unique_together = (('event', 'badge_type'),)

    def save(self, **kwargs):
        self.updated_on = datetime.now()
        super(Badge, self).save(**kwargs)

    def image_preview(self):
        """Return HTML fragment to display badge image."""
        h = '<img src="%s" alt="Event badge"/>' % self.image.url
        return mark_safe(h)
    image_preview.allow_tags = True
    image_preview.short_description = 'image'

    @property
    def bg_image_path(self):
        """Return path to the badge's background image."""
        return self.BADGE_BG_IMAGES[self.badge_type]

    @property
    def img_width(self):
        return self.image_width or self.image.width

    @property
    def img_height(self):
        return self.image_height or self.image.height


class Stats(models.Model):
    """A model that maintains an event's salient statistics."""
    event = models.ForeignKey(Event, unique=True)
    num_attendees = models.PositiveIntegerField(default=0, blank=True)
    num_views = models.PositiveIntegerField(default=0, blank=True, db_index=True)
    num_owner_views = models.PositiveIntegerField(default=0, blank=True, db_index=True)
    updated_on = models.DateTimeField(default=datetime.now, blank=True, db_index=True)

    class Meta:
        verbose_name_plural = 'stats'

    def save(self, **kwargs):
        self.updated_on = datetime.now()
        if not self.num_attendees:
            self.num_attendees = 0
        super(Stats, self).save(**kwargs)

    @property
    def views(self):
        return self.num_views
    
    
class AttendeeManager(models.Manager):
    def active(self):
        q = self.exclude(
             ~models.Q(event__ext_event_source='') & 
             models.Q(attendee_profile__pk=models.F('event__creator__pk'))
        )
        return q


class Attendee(models.Model):
    """Model for an event attendee."""
    event = models.ForeignKey(Event)
    attendee = models.ForeignKey(User)
    attendee_profile = models.ForeignKey(UserProfile)
    qty = models.PositiveIntegerField('quantity', default=1)
    added_on = models.DateTimeField(blank=True, default=datetime.now, db_index=True)
    
    objects = AttendeeManager()

    def __unicode__(self):
        return u'%s is in for %s (%s)' % (self.attendee_profile.username, self.event.title, self.event.pk)
    
    def get_absolute_url(self):
        return self.event.get_absolute_url()

    class Meta:
        ordering = ('-added_on',)

    def save(self, **kwargs):
        if not self.added_on:
            self.added_on = datetime.now()
        is_new = not self.pk
        if is_new:
            self.attendee = self.attendee_profile.user
        super(Attendee, self).save(**kwargs)
        if is_new:            
            ActionItem.objects.q_attendee_action(self, 'event-faved')
        clear_keys('attendees', self.event.pk)
        # propagate this event to the attendee's friends:
        tasks.recommend_event_to_friends(self.attendee_profile.pk, self.event.pk)
        # remove this event from recommended events for this user:
        self.attendee_profile.recommendedevent_set.filter(event=self.event).delete()

    def delete(self, **kwargs):
        clear_keys('attendees', self.event.pk)
        ActionItem.objects.q_attendee_action_done(self, 'event-faved')
        super(Attendee, self).delete(**kwargs)


class RecommendedEvent(models.Model):
    """Event recommended for a user"""
    user_profile = models.ForeignKey(UserProfile)
    event = models.ForeignKey(Event)
    num_friends = models.PositiveIntegerField(default=1)
    added_on = models.DateTimeField(blank=True, default=datetime.now, db_index=True)
    updated_on = models.DateTimeField(blank=True, default=datetime.now, db_index=True)

    def __unicode__(self):
        return u'%s, %s' % (self.event.pk, self.user_profile.username)

    class Meta:
        unique_together = (('user_profile', 'event'),)
        ordering = ('-added_on',)

    def save(self, **kwargs):
        if not self.added_on:
            self.added_on = datetime.now()
        self.updated_on = datetime.now()
        super(RecommendedEvent, self).save(**kwargs)


def recompute_event_stats(sender, instance, **kwargs):
    """When an ``Attendee`` object is saved, schedule a recomputation
    of the event's statistics.

    """
    if isinstance(instance, Attendee):
        instance.event.recompute()
        # ActionItem.objects.q_event_action(instance.event, 'recompute-event')

signals.post_save.connect(recompute_event_stats, sender=Attendee)
signals.post_delete.connect(recompute_event_stats, sender=Attendee)


class EventTweetManager(models.Manager):
    def delete_tweets_for_event(self, event, min_pk=0):
        """Remove all auto-generated tweets for given event"""
        cursor = connection.cursor()
        db_table = quote_name(self.model._meta.db_table)
        
        if min_pk:
            sql = '''DELETE FROM %s WHERE event_id=%%s AND is_onsite=%%s AND id <= %%s''' % db_table
            params = [event.pk, False, min_pk]
        else:
            sql = '''DELETE FROM %s WHERE event_id=%%s AND is_onsite=%%s''' % db_table
            params = [event.pk, False]        

        cursor.execute(sql, params)
        transaction.commit_unless_managed()
        
    def tweets(self, event=None, limit=settings.EVENT_MAX_TWEETS, source=None, is_retweet=False):
        q = self.filter(is_onsite=False)
        if not is_retweet:
            q = q.filter(is_retweet=False)
        if source:
            q = q.filter(source=source)
        if event:
            q = q.filter(event=event)
        q = q.order_by('-added_on')
        if limit:
            q = q[:limit]
        return q

    def max_tweet_id(self, event=None, exclude_onsite=True, source='twitter'):
        q = self
        if exclude_onsite:
            q = q.exclude(is_onsite=True)
        if source:
            q = q.filter(source=source)
        if event:
            q = q.filter(event=event)
        d = q.aggregate(models.Max('tweet_id'))
        return d.get('tweet_id__max', 0)

    def onsite_tweet_id_set(self, event=None, source='twitter', limit=30000):
        return self.tweet_id_set(event, True, source, limit=limit)

    def tweet_id_set(self, event=None, onsite_only=False, source='twitter', limit=30000):
        q = self
        if onsite_only:
            q = q.filter(is_onsite=True)
        if source:
            q = q.filter(source=source)
        if event:
            q = q.filter(event=event)
        if limit:
            q = q.order_by("-pk")[:limit]
        return set(list(q.values_list('tweet_id', flat=True)))


class EventTweet(models.Model):
    """Event Tweets"""
    event = models.ForeignKey(Event)
    is_onsite = models.BooleanField(db_index=True, default=False, help_text=u"True if this was tweeted from our site")
    tweet_id = models.CharField(max_length=30, db_index=True)
    from_user = models.CharField(max_length=50, db_index=True)
    text = models.TextField()
    profile_image_url = models.URLField(max_length=255, verify_exists=False)
    tweet_json = models.TextField()
    is_retweet = models.BooleanField(default=False, db_index=True)
    source = models.CharField(max_length=30, default='twitter', db_index=True)
    added_on = models.DateTimeField(blank=True, default=datetime.now, db_index=True)

    objects = EventTweetManager()

    def __unicode__(self):
        return u'%s: %s' % (self.from_user, self.text[:50])

    class Meta:
        unique_together = (('event', 'tweet_id', 'source'),)
        ordering = ('-added_on',)

    def set_tweet(self, tweetdict, do_save=False):
        self.tweet_json = json.dumps(tweetdict)
        self.tweet_id = unicode(tweetdict['id'])
        self.text = tweetdict['text']
        if 'from_user' in tweetdict: # search result format
            self.from_user = tweetdict['from_user']
        else: # status format
            self.from_user = tweetdict['user']['screen_name']
        if 'profile_image_url' in tweetdict: # search result format
            self.profile_image_url = tweetdict['profile_image_url']
        else: # status format
            self.profile_image_url = tweetdict['user']['profile_image_url']
        self.is_retweet = tweetdict['text'].startswith(u'RT ')
        self.added_on = convert_timestamp(tweetdict['created_at'], tweetdict)
        if do_save:
            super(EventTweet, self).save()

    def get_tweet(self):
        return json.loads(self.tweet_json)
    
    def get_profile_image_url(self):
        if settings.TWITTER_USE_TWEETIMAGES:
            return u"http://img.tweetimag.es/i/%s_n" % self.from_user
        else:
            return self.profile_image_url

    tweet = property(get_tweet, set_tweet)


class EventCreatedSignal(models.Model):
    event = models.ForeignKey(Event, unique=True)
    added_on = models.DateTimeField(blank=True, default=datetime.now, db_index=True)
    
    def save(self, **kwargs):
        if not self.added_on:
            self.added_on = datetime.now()
        super(EventCreatedSignal, self).save(**kwargs)


class FoursquareTrend(models.Model):
    venue = models.ForeignKey(Venue)
    fsq_id = models.CharField(max_length=64, default='', blank=True, db_index=True, editable=True)
    fsq_checkins = models.IntegerField(default=0, null=True, blank=True, db_index=True, editable=True)
    fsq_ratio = models.CharField(max_length=25, default=u'', blank=True, db_index=True, editable=True)
    fsq_m = models.IntegerField(default=0, null=True, blank=True)
    fsq_f = models.IntegerField(default=0, null=True, blank=True)
    fsq_mf = models.DecimalField(blank=True, null=True, max_digits=10, decimal_places=2)
    fsq_fm = models.DecimalField(blank=True, null=True, max_digits=10, decimal_places=2)
    updated_on = models.DateTimeField(default=datetime.now, editable=False, db_index=True)

    class Meta:
        ordering = ('-updated_on',)

    def __unicode__(self):
        return self.fsq_id

    def save(self, *args, **kwargs):
        self.updated_on = datetime.now()
        if not self.fsq_mf:
            self.fsq_mf = 0
        if not self.fsq_fm:
            self.fsq_fm = 0
        if not self.fsq_m:
            self.fsq_m = 0
        if not self.fsq_f:
            self.fsq_f = 0
        super(FoursquareTrend, self).save(*args, **kwargs)
        
        
class EventCheckinManager(models.Manager):
    def connect_profiles_to_checkins(self, checkin_uids, uid_userprofile_dict):  
        """Update user_profile for EventCheckin instances where fsq_userid matches the 
        given checkin_uids.
        
        `uid_userprofile_dict` is a map of fsq_userid -> user_profile instance.
        
        """      
        threshold_dt = date.today() - timedelta(days=10)
        q = self.filter(event__event_date__gt=threshold_dt, user_profile__isnull=True)
        for usr in chunks(checkin_uids, 100):
            if not usr:
                break
            ex = q.filter(fsq_userid__in=usr)
            for ec in ex:
                up = uid_userprofile_dict.get(ec.fsq_userid, None)
                if up:
                    ec.user_profile = up
                    ec.save()
        
        
class EventCheckin(models.Model):
    event = models.ForeignKey(Event)
    user_profile = models.ForeignKey(UserProfile, null=True, blank=True)
    fsq_userid = models.CharField(max_length=64, db_index=True, editable=True)
    checkin_time = models.DateTimeField(default=datetime.now, db_index=True)
    unlocked = models.BooleanField(default=False, db_index=True)
    updated_on = models.DateTimeField(default=datetime.now, editable=False, db_index=True)
    
    objects = EventCheckinManager()

    class Meta:
        ordering = ('-updated_on',)        

    def __unicode__(self):
        if self.user_profile:
            return u"%s unlocked %s" % (self.user_profile, self.event)
        else:
            return self.fsq_userid
    
    def get_absolute_url(self):
        return self.event.get_absolute_url()

    def save(self, *args, **kwargs):
        just_unlocked = not self.pk
        self.updated_on = datetime.now()
        if not self.checkin_time:
            self.checkin_time = datetime.now()
        self.unlocked = self.event.has_unlock
        if not self.user_profile:
            try:
                self.user_profile = UserProfile.objects.filter(fsq_userid=self.fsq_userid).order_by('-pk')[0]
                just_unlocked = True
            except:
                pass        
        super(EventCheckin, self).save(*args, **kwargs)
        if just_unlocked and self.user_profile and (self.event.has_unlock or settings.FOURSQUARE_UNLOCK_BETA):
            ActionItem.objects.q_eventcheckin_action(self, 'event-unlocked')
