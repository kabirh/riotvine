"""

LastFM event scraper

"""
import os
import os.path
import threading
import logging, logging.config
import sys
import getopt
import string
import time
import socket
import urllib2
from uuid import uuid4
from datetime import date, datetime, timedelta

if not os.environ.get('DJANGO_SETTINGS_MODULE', False):
    os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

from django.conf import settings
from django.utils import simplejson as json
from django.utils.http import urlencode
from django.core.files.base import ContentFile


# Configure logging here before we import any of our other classes that make use
# of a logger. If this is not done, the default logging configuration defined by 
# the web application gets invoked first.
threading.currentThread().setName('LastFM') # Used by the logger
if not logging.getLogger().handlers:
    logging.config.fileConfig('./lastfm_logging.conf')
    _x_root = logging.getLogger()
    _x_root.setLevel(settings.LOG_DEBUG and logging.DEBUG or logging.INFO)

_x = logging.getLogger('event.lastfm')
_log = _x # synonym

from django.contrib.auth.models import User
from event.models import Event, Venue
from artist.models import ArtistProfile
from registration.models import UserProfile
from rdutils.text import slugify
from registration.utils import copy_avatar_from_url_to_profile, is_username_available


_DATE_FORMAT = "%a, %d %b %Y" # format: Tue, 07 Jul 2009
_PARAMS = {
    'url':getattr(settings, 'LASTFM_API_URL', 'http://ws.audioscrobbler.com/2.0/'),
    'api_key':settings.LASTFM_API_KEY,
    'location':'Boston,+United+States',
}
_URL = u"%(url)s?method=geo.getevents&format=json&location=%(location)s&api_key=%(api_key)s"
_ARTIST = ArtistProfile.objects.get(url='riotvine-member')
_TODAY = date.today()
_UPDATE_EXISTING = getattr(settings, 'LASTFM_UPDATE_EXISTING', False)
_UI_MEDIA_ROOT = os.path.join(settings.MEDIA_ROOT, settings.UI_ROOT, 'internal')
_DEFAULT_IMAGE = os.path.join(_UI_MEDIA_ROOT, settings.EVENT_BADGE_DEFAULT_IMAGE)
f = open(_DEFAULT_IMAGE, "rb")
_DEFAULT_IMG = f.read()
f.close()

_ARTISTINFO_URL = u"%(url)s?method=artist.getInfo&format=json&api_key=%(api_key)s"


def get_events(url, page=1, loc=None):
    fullurl=  u'%s&page=%s' % (url, page)
    req = urllib2.Request(fullurl)
    req.add_header("Content-type", "application/x-www-form-urlencoded")
    req.add_header('User-Agent', settings.USER_AGENT)
    try:
        resp = urllib2.urlopen(req)
    except Exception, e:
        # retry once
        time.sleep(20)
        resp = urllib2.urlopen(req)
    ret = resp.read()
    resp.close()
    results = json.loads(ret)
    try:
        if results:
            events = results.get('events', {}).get('event', [])
            attr = results.get('events', {}).get('@attr', {})
        else:
            events, attr = [], {}
    except Exception, e:
        _x.warn("Result JSON could not be processed:\n(%s)\nURL:\n%s", ret, fullurl)
        _x.exception(e)
        events, attr = [], {}
    meta = {
        'location':attr.get('location', ''),
        'page':int(attr.get('page', '1')),
        'totalpages':int(attr.get('totalpages', '1')),
        'total':int(attr.get('total', '1')),
    }
    return events, meta


def is_event_in_db(lastfm_id):
    try:
        return Event.objects.get(lastfm_id=lastfm_id)
    except Event.DoesNotExist:
        return None


def get_raw_image(url):
    try:
        if not url:
            f = open(_DEFAULT_IMAGE, "rb")
            img = f.read()
            f.close()
            return img
        time.sleep(0.02)
        req = urllib2.Request(url)
        req.add_header("Content-type", "application/x-www-form-urlencoded")
        req.add_header('User-Agent', settings.USER_AGENT)
        resp = urllib2.urlopen(req)
        ret = resp.read()
        resp.close()
        return ret
    except Exception, e:
        return _DEFAULT_IMAGE
    

def get_artist_info(name):
    """Last.FM artist info"""
    try:
        url = _ARTISTINFO_URL % _PARAMS        
        fullurl=  u'%s&%s' % (url, urlencode({'artist':name}))
        _x.debug(fullurl)
        req = urllib2.Request(fullurl)
        req.add_header("Content-type", "application/x-www-form-urlencoded")
        req.add_header('User-Agent', settings.USER_AGENT)
        try:
            resp = urllib2.urlopen(req)
        except Exception, e:
            # retry once
            time.sleep(20)
            resp = urllib2.urlopen(req)
        ret = resp.read()
        resp.close()
        results = json.loads(ret)
        return results
    except Exception, e:
        return {}


def name_to_username(name):
    """Convert names of the form 'Rajesh Dhawan' to 'RajeshDhawan'"""
    chars = string.ascii_letters + string.digits
    username = ''.join([x for x in name.title() if x in chars])
    return username[:30]


def get_artist_user_profile(name):
    """Return existing artist profile or create a new one and return it"""
    if not name:
        return _ARTIST.user_profile
    name = name.strip()
    if not name:
        return _ARTIST.user_profile
    is_dirty = False
    try:
        user_profile = UserProfile.objects.get(full_artistname=name)
        _log.debug("Reusing existing artist profile")
    except UserProfile.DoesNotExist:
        # create user profile from last fm data
        n = name.split(' ')
        if len(n) == 2:
            first_name, last_name = n
        elif len(n) > 2:
            first_name = n[0]
            last_name = u' '.join(n[1:])
        else:
            first_name = n
            last_name = ''
        username = name_to_username(name)
        if not username:
            return _ARTIST.user_profile
        username = username.strip()
        if not is_username_available(username):
            username = username + "-"
        a, created = User.objects.get_or_create(
            username=username,
            defaults = dict(
                first_name=first_name[:30],
                last_name=last_name[:30],
                email='riotvine-artist-%s@riotvine.com' % username.lower(),
                is_staff=False,
                is_active=True,                
            )
        )
        user_profile = a.get_profile()
        if created:
            user_profile.send_reminders = False
            user_profile.send_favorites = False
            user_profile.is_verified = True
            user_profile.permission = 'everyone'
            is_dirty = True  
            _log.debug("Using newly created artist profile")
    if not user_profile.full_artistname:
        user_profile.full_artistname = name
        is_dirty = True
    if not user_profile.avatar:
        # download profile image from last.fm
        info = get_artist_info(name)
        if info:
            imagelist = info.get('artist', {}).get('image', [])
            if imagelist:
                url = get_image_url(imagelist)
                copy_avatar_from_url_to_profile(url, user_profile)
                is_dirty = False
    if is_dirty:
        user_profile.save()
    return user_profile 
    

def try_merge(event):
    """Attempt a merge into an existing lastfm event if this is a duplicate.

    Spec:
    -------
    Fix the last.fm feed so that when an event is modified, it doesn't 
    re-create the event. Compare Venue/Date and Time if available to see if 
    the events are the same. If Time is unavailable, compare the list of 
    artists to see if there are matches. If there are, hide the secondary 
    event. If the secondary event has fields with data in them that the 
    original event does not, merge the data.

    """
    q = Event.objects.active().exclude(lastfm_id__isnull=True).exclude(lastfm_id=u'')
    q = q.filter(
        location=event.location,
        venue__name__iexact=event.venue.name,
        event_date=event.event_date,
    )
    for e in q:
        if not event._has_start_time:
            # compare headliners because secondary event does not have a start time
            if e.headliner and event.headliner == e.headliner:
                return e
        elif e.event_start_time == event.event_start_time:
            return e
    return None


def get_image_url(imagelist, key='extralarge'):
    for x in imagelist:
        if x['size'] == key:
            image = x['#text']
            return image
    return None


def insert(events, loc):
    """Iterate through event list and insert into DB"""
    n = 0
    type_errors = 0
    for e in events:
        try:
            lfm_id = e['id']
        except TypeError, te:
            _log.warn("Skipped TypeError on badly formatted event data: %s" % e)
            type_errors += 1
            continue
        existing_event = is_event_in_db(lfm_id)
        if existing_event and not _UPDATE_EXISTING:
            continue # skip events that already exist in DB
        image, image_content = None, None
        image = get_image_url(e['image'])
        if not image:
            continue # We can't work without a badge image
        event_date = e['startDate'] # format: Tue, 07 Jul 2009
        dtx = event_date.split(' ')
        event_date = ' '.join(dtx[:4]) # discard any time component
        dt = time.strptime(event_date, _DATE_FORMAT)
        event_date = date(*dt[:3])
        if event_date < _TODAY:
            continue # Ignore past events
        venue_url = e['venue']['url']
        if not venue_url:
            continue # Don't accept bad venues

        title = e['title']
        website = e['website']
        desc = e['description']
        headliner = e['artists'].get('headliner', '')
        artist_list = set([a for a in e['artists']['artist'] if len(a) > 1 and a != headliner])
        if not artist_list:
            if headliner:
                artist_list = []
            else:
                artist_list = [title]
        full_list = list(artist_list)
        if headliner:
            full_list.insert(0, headliner)
        csv_artist_list = full_list and u",".join(full_list) or u""
        quoted_list = [u'"%s"' % a for a in full_list]
        hashtag = u",".join(quoted_list)
        art_html = [u"<li>%s</li>" % a for a in artist_list]        
        if headliner:
            art_html.insert(0, u'<li class="headliner">%s</li>' % headliner)
        art_html = u"<h4 class='artist_title'>Artists</h4><ul class='artist_list'>%s</ul>\n" % u"\n".join(art_html)
        desc = u"%s%s" % (art_html, desc)
        venue = e['venue']['name'].strip()
        venue_address = e['venue']['location']['street'].strip()
        venue_city = e['venue']['location']['city'].strip()
        venue_zip = e['venue']['location']['postalcode'].strip()
        if headliner and venue and headliner == title:
            # Change title format to:
            # headliner at venue name! mm/dd
            mm_dd = event_date.strftime("%m/%d")
            title = u"%s at %s! %s" % (headliner, venue, mm_dd)
            if len(title) > 120:
                title = u"%s.." % title[:118]
        lat, lng = None, None
        source = ''
        if e['venue']['location'].get("geo:point", {}).get("geo:lat", None):
            lat = e['venue']['location']["geo:point"]["geo:lat"]
            lng = e['venue']['location']["geo:point"]["geo:long"]
            lat = str(round(float(lat), 3))
            lng = str(round(float(lng), 3))
            source = u"%s,%s" % (lat, lng)
        tz = e['venue']['location'].get('timezone', '')
        event_time = e.get('startTime', "21:00")
        has_start_time = 'startTime' in e
        image_content = ContentFile(get_raw_image(image))
        fname, ext = os.path.splitext(image)
        fname = u'%s%s' % (uuid4().hex[::2], ext)        
        vn, created = Venue.objects.get_or_create(
            name=venue[:255],
            geo_loc=source,
            defaults=dict(
                source='last-fm',
                address=venue_address[:255],
                city=venue_city[:255],
                zip_code=venue_zip[:12],
                venue_url=venue_url[:255],
            )
        )
        if False and not created and vn.source != 'last-fm':
            # Update empty fields
            dirty = False
            if not vn.address:
                vn.address = venue_address[:255]
                dirty = True
            if not vn.city:
                vn.city = venue_city[:255]
                dirty = True
            if not vn.zip_code:
                vn.zip_code = venue_zip[:12]
                dirty = True
            if not vn.venue_url:
                vn.venue_url = venue_url[:255]
                dirty = True
            if dirty:
                vn.save()
        if existing_event:
            # only update title on this existing event
            existing_event.title = title[:120]
            super(Event, existing_event).save()
            _x.debug("Updated title for %s", existing_event)
        else:
            user_profile = get_artist_user_profile(headliner)
            ex = Event(
                lastfm_id = lfm_id,
                artist=_ARTIST,
                creator=user_profile,
                is_submitted=True,
                is_approved=True,
                title=title[:120],
                url=(u"%s-%s" % (slugify(title)[:30], uuid4().hex[::4]))[:35],
                description=desc,
                venue=vn,
                event_date=event_date,
                event_start_time=event_time,
                event_timezone=tz,
                hashtag=u'', # hashtag[:250], # don't fetch tweets for last.fm generated events (3/23/2010)
                location=loc,
                headliner=headliner[:200] or u'',
                artists=csv_artist_list[:250] or u'',
                ext_event_source='last.fm',
            )
            ex._has_start_time = ex.event_start_time and has_start_time
            ey = try_merge(ex)
            if ey:
                # new event is a duplicate; hide it
                ex.is_deleted = True
                _x.warn("Merged %s into %s", ex, ey)
            ex.image.save(fname, image_content, save=False)
            ex._create_resized_images(raw_field=None, save=False)
            ex.save()
            ex.attendee_set.get_or_create(attendee_profile=user_profile)
            _x.debug("Saved %s", ex)
        n += 1
    if type_errors:
        _x.warn("%s TypeErrors on events:\n%s", type_errors, events)
    return n


def do_process():
    socket = _check_instance_ok()
    if not socket:
        return 0
    n = 0
    npages = 0
    for loc, params in settings.LOCATION_DATA.iteritems():
        m = 0
        lfm_city = params[2]
        _PARAMS['location'] = lfm_city
        url = _URL % _PARAMS
        _x.info(url)
        events, meta = get_events(url, 1, loc)
        npages += 1
        pages = meta['totalpages']
        n += insert(events, loc)
        if pages > 1:
            pages = min(pages, settings.LASTFM_MAX_PAGES)
            for page in range(2, pages+1):
                time.sleep(1)
                events, meta = get_events(url, page, loc)
                d = insert(events, loc)
                n += d
                m += d
                npages += 1
        _x.info("Processed %s events for %s", m, loc)
    _x.debug("Pages downloaded %s", npages)
    _x.info("Processed %s events total", n)
    return n


def do_process_loop():
    _x.info('LastFM processor started. Hit Ctrl-C to exit.')
    try:
        do_process()
    except KeyboardInterrupt, k:
        pass
    finally:
        _x.info("LastFM processor stopped.")


def _check_instance_ok():
    """Return True if this instance of the script is OK to be executed.

    If multiple instances of this script are not allowed to be run, 
    settings.LASTFM_SCRIPT_LOCK_PORT must be defined to be a TCP/IP port number.

    This method binds to that port number. If the bind call is successful,
    it means that this instance is the first one to start. Subsequent instances
    would fail to bind to this port and thus know that they are not the first 
    instance.

    """
    if not hasattr(settings, 'LASTFM_SCRIPT_LOCK_PORT'):
        # Multiple instances are allowed
        return True
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('', settings.LASTFM_SCRIPT_LOCK_PORT))
        return s
    except socket.error, e:
        _x.warn('Another instance is running.')
        _x.error(e)
        return None


class Usage(Exception):
    def __init__(self, msg):
        self.msg = msg


def run_script(argv=None):
    """LastFM Processor
-h, --help      This help
"""
    if argv is None:
        argv = sys.argv
    try:
        try:
            opts, args = getopt.getopt(argv[1:], "h", ["help"])
        except getopt.GetoptError, msg:
            raise Usage(msg)
        for o, a in opts:
            if o in ("-h", "--help"):
                print run_script.__doc__
                return 0
        do_process_loop()
        return 0
    except Usage, err:
        print >> sys.stderr, err.msg
        print >> sys.stderr, "For help, use --help"
        return 2


if __name__ == "__main__":
    sys.exit(run_script())

