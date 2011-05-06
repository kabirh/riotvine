import logging
import os.path
from urllib2 import urlopen, Request, urlparse, URLError
from time import time, strptime, sleep
from datetime import date, datetime, timedelta
from dateutil import parser as dtparser
from dateutil import tz
from itertools import chain
from collections import defaultdict
from uuid import uuid4

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.urlresolvers import resolve, Resolver404
from django.contrib.flatpages.models import FlatPage
from django.utils import simplejson as json
from django.utils.http import urlencode
from django.db.models import Count
from django.utils.hashcompat import sha_constructor
from django.db import transaction, connection

from rdutils.email import email_template
from rdutils.cache import shorten_key, cache
from rdutils.url import download_url
from registration.models import Friendship, UserProfile, Follower
from rdutils.text import slugify


_log = logging.getLogger('event.utils')

_UI_MEDIA_ROOT = os.path.join(settings.MEDIA_ROOT, settings.UI_ROOT, 'internal')
_DEFAULT_IMAGE = os.path.join(_UI_MEDIA_ROOT, settings.EVENT_BADGE_DEFAULT_IMAGE)


def make_invoice_num(campaign, user):
    return '%s-%s-%s' % (campaign.pk, user.pk, int(time()))


def clean_address(address, city, state, zip):
    """Given address, city and state in various forms, return canonical versions of them
    
    Examples of bad formats (address - city - state):
        Any - Cambridge, MA - None
        Any - Boston, Massachuesetts - None
        Any - Framingham (MA) - None
        Any - Boston(, MA) - None
        None - 158 Brighton Ave., Allston, MA, 02134 - None (This one is not cleaned up)
    """
    if not address:
        # if a address is not present, abort any clean up
        return address, city, state, zip
    if not city:
        city = u''
    if not state:
        state = u''
    city = city.strip()
    state = state.strip()
    if city:
        city = city.replace(')', '').replace('(,', ',').replace(' (', ',')
    if city and not state:
        if ',' in city: # city already has state name in it: Boston, MA or Cambridge, Massachusetts
            x = city.split(',')
            if len(x) > 1:
                city, state = x[0].strip(), x[1].strip()
    if state and state.lower().startswith("massachu"):
        state = u'MA'
    if city and not state:
        state = u''
    return address, city, state, zip
    


def is_event_url_available(url, event=None):
    """Check that ``url`` is not already in use.

    A ``url`` is in use if it's been taken by another event or 
    it's being used internally by this web application.

    Furthermore, ``url`` must resolve to the event public page view.

    """
    from event.views import view_seo
    from event.models import Event
    # Check if this URL maps to internal site features.
    rel_url = '/riotvine-member/show/%s/' % url.lower()
    f = FlatPage.objects.filter(url__endswith=url.lower()).count()
    if f > 0: # URL maps to a flatpage.
        return False
    try:
        fn_tuple = resolve(rel_url)
        # Ensure that the url resolves to the correct view.
        if fn_tuple[0] != view_seo:
            return False
    except Resolver404:
        return False
    # Check if another event has claimed this url.
    q = Event.objects.filter(url__iexact=url)
    if event and event.pk:
        q = q.exclude(pk=event.pk)
    match = q.count()
    is_url_available = match == 0
    return is_url_available


def get_friendly_attendees(user_profile):
    """Get active event attendees that are friends or followees of user_profile.

    Return a list of tuples of the form:
        [(event_id, friend_profile_id),...]

    """
    from event.models import Attendee, Event
    now = date.today()
    # events that this user's friends are interested in:
    xlist = list(Attendee.objects.filter(
        event__is_deleted=False,
        event__is_approved=True,
        event__event_date__gte=now,
        attendee_profile__friends2__user_profile1=user_profile
    ).values_list("event_id", "attendee_profile_id")[:20000])
    # events that this user's friends have created:
    xlist2 = list(Event.objects.active().filter(
        creator__friends2__user_profile1=user_profile
    ).values_list("id", "creator_id")[:10000])
    xlist.extend(xlist2)
    # events that this user's followees are interested in:
    xlist3 = list(Attendee.objects.filter(
        event__is_deleted=False,
        event__is_approved=True,
        event__event_date__gte=now,
        attendee_profile__followees__follower=user_profile,
        attendee_profile__followees__followee__permission__in=('everyone', 'only-riotvine-users'),
    ).values_list("event_id", "attendee_profile_id")[:20000])
    xlist.extend(xlist3)
    # events that this user's followees have created:
    xlist4 = list(Event.objects.active().filter(
        creator__followees__follower=user_profile,
        creator__followees__followee__permission__in=('everyone', 'only-riotvine-users'),
    ).values_list("id", "creator_id")[:10000])
    xlist.extend(xlist4)
    return xlist


@transaction.commit_on_success
def build_recommended_events(user_profile):
    """Build recommended events for a user, based on his friends' and followees' calendar events"""
    from event.models import RecommendedEvent, Event
    if not isinstance(user_profile, UserProfile):
        pk = user_profile
        try:            
            user_profile = UserProfile.objects.get(pk=pk)
        except UserProfile.DoesNotExist:
            _log.warn("UserProfile does not exist for profile id %s (build_recommended_events)", pk)
            return
    user_events = set(Event.objects.active().filter(
        attendee__attendee_profile=user_profile
    ).distinct().values_list("id", flat=True)) # events already in this user's calendar
    recs = user_profile.recommendedevent_set
    all_recs = recs.all()
    # remember added_on dates for current recommendations
    datemap = {}
    for rx in all_recs:
        key = u"%s:%s" % (rx.user_profile_id, rx.event_id)
        datemap[key] = rx.added_on
    all_recs.delete() # clear current recommendations before computing a fresh set of recommendations
    attendees = get_friendly_attendees(user_profile)
    _log.debug("For user %s, reco attendees: %s", user_profile, attendees)
    mapper = lambda x:(x[0], 1) # count each friend once per event
    rec_map = defaultdict(int)
    for event, fr in map(mapper, attendees):
        if event not in user_events: # only recommend events this user doesn't have in her own calendar            
            rec_map[event] += fr
    # now rec_map has been populated with: event_id -> num_friends
    cursor = connection.cursor()
    rtab = RecommendedEvent._meta.db_table
    n = 0
    now = datetime.now()
    for ev_id, num_friends in rec_map.items():
        key = u"%s:%s" % (user_profile.pk, ev_id)
        added_on = datemap.get(key, now)
        cursor.execute(
            '''
                INSERT INTO %s (user_profile_id, event_id, num_friends, added_on, updated_on)
                VALUES (%%s, %%s, %%s, %%s, %%s)
            ''' % rtab,
            [user_profile.pk, ev_id, num_friends, added_on, now]
        )
        n += 1
    if n:
        transaction.set_dirty()
    rec_map.clear()
    _log.debug("Event recommendations rebuilt for user %s" % user_profile.pk)


@transaction.commit_on_success
def recommend_event_to_friends(user_profile, event):
    """Recommend this event to user_profile's friends and followers"""
    from event.models import Event
    if not isinstance(user_profile, UserProfile):
        pk = user_profile
        try:            
            user_profile = UserProfile.objects.get(pk=pk)
        except UserProfile.DoesNotExist:
            _log.warn("UserProfile does not exist for profile id %s (recommend_event_to_friends)", pk)
            raise
    friends_only = user_profile.permission == 'only-friends'
    friendships = Friendship.objects.get_friendships(user_profile)    
    if friends_only:
        if not friendships:
            return
    if not isinstance(event, Event):
        try:
            event = Event.objects.get(pk=event)
        except Event.DoesNotExist:
            return
    re = event.recommendedevent_set
    attendees = set(event.attendee_set.values_list('attendee_profile_id', flat=True))
    if friendships:
        for fr in friendships:
            p = fr.user_profile2 # friend's profile
            if p.pk in attendees:
                continue # this friend already has this event in her calendar
            obj, created = re.get_or_create(user_profile=p, defaults={'num_friends':1})
            if not created: 
                # updated existing recommendation; so increment friend count
                obj.num_friends += 1
                obj.save()
            attendees.add(p.pk)
    if friends_only:
        return
    # recommend to followers too
    followers = Follower.objects.select_related('follower__user').filter(followee=user_profile, follower__user__is_active=True)
    if followers:
        for fr in followers:
            p = fr.user_profile2 # friend's profile
            if p.pk in attendees:
                continue # this friend already has this event in her calendar
            obj, created = re.get_or_create(user_profile=p, defaults={'num_friends':1})
            if not created: 
                # updated existing recommendation; so increment friend count
                obj.num_friends += 1
                obj.save()
            attendees.add(p.pk)


def send_email_to_friends_of_event_creator(event):
    from registration.models import Friendship
    _log.debug("Sending email to friends of the creator of event %s", event)
    _log.debug("Creator %s", event.creator)
    creator = event.creator
    ctx = {'event':event, 'creator':creator, 'event_url':event.get_absolute_url(force_hostname=True)}
    subject = u'%s posted %s' % (creator.username, event.title)
    sent_emails = set() 
    for f in Friendship.objects.get_friendships(creator):
        friend = f.user_profile2 # friend's profile
        if friend.send_favorites:
            email = friend.user.email
            if email not in sent_emails: # don't send duplicate emails
                ctx['username'] = friend.username
                ctx['firstname'] = friend.user.first_name
                email_template(subject, 'event/email/event_added.html', ctx,to_list=[email])
                sent_emails.add(email)
    _log.debug("Sent %s emails to friends of %s", len(sent_emails), creator)
    sent_emails.clear()


def process_event_created_signals():    
    from event.models import Event, EventCreatedSignal
    threshold = datetime.now() - timedelta(seconds=getattr(settings, 'EVENT_CREATION_SIGNAL_THRESHOLD', 600))
    threshold_start = threshold - timedelta(hours=48)
    events = Event.objects.active().filter(eventcreatedsignal__added_on__lte=threshold, eventcreatedsignal__added_on__gte=threshold_start)
    ex = EventCreatedSignal.objects.filter(added_on__lte=threshold, added_on__gte=threshold_start)
    num = 0
    try:
        for event in events:
            send_email_to_friends_of_event_creator(event)
            num += 1
    except Exception, e:
        _log.exception(e)
    ex.delete()
    return num


def send_event_reminder(reminder_dict):
    etype = reminder_dict.get('email_type', 'reminder')
    if etype == 'favorites':
        email_template(
            'Your friends have shared events with you',
            'event/email/event_favorites.html',
            {'data':reminder_dict},
            to_list=[reminder_dict['attendee__email']]
        )
    else:
        subject = u'Reminder: %s' % reminder_dict['event__title']
        n = reminder_dict.get('fsq_checkins', 0) 
        if n:
            if n == 1:
                append = u' (%s person here)' % n
            else:
                append = u' (%s people here)' % n
            subject = subject + append
        email_template(
            subject,
            'event/email/event_reminder.html',
            {'data':reminder_dict},
            to_list=[reminder_dict['attendee__email']]
        )


@transaction.commit_on_success
def save_event_tweets(event_id, tweets, do_reset=False):
    """Save a list of tweets for the event.

    Discard duplicate tweets by id.

    """
    from event.models import Event, EventTweet
    try:
        e = Event.objects.active().get(pk=event_id)
    except Event.DoesNotExist:
        return
    do_user_message = e.show_creator and not e.eventtweet_set.count()
    if do_reset:
        # delete current tweets
        e.eventtweet_set.delete_tweets_for_event(event=e)
        _log.warn("Reset tweets for event %s", e.pk)
    currset = EventTweet.objects.tweet_id_set(e) # IDs of event tweets that already exist in DB
    for t in tweets:
        if unicode(t['id']) not in currset:
            et = EventTweet(event=e)
            et.tweet = t # force JSONification and parsing of fields
            et.save()
    e.tweet_count = e.eventtweet_set.count()
    if do_user_message and e.tweet_count:
        url = {'url':e.get_absolute_url()}
        e.owner.message_set.create(message='''Whoa! <a href="%(url)s">Your event has got some tweets now&nbsp;&raquo;</a>''' % url)
    super(Event, e).save() # save via super to avoid reinvoking hooks attached to e.save()


def copy_background_image_from_url_to_event(url, event, commit=False):
    """Download Twitter background image from URL and associate it with the given event"""
    if url:
        try:
            _log.debug("Downloading background pic from %s", url)
            filename = os.path.basename(urlparse.urlparse(url).path)
            request = Request(url)
            request.add_header('User-Agent', settings.USER_AGENT)
            response = urlopen(request)
            image_content = ContentFile(response.read())
            response.close()
            event.bg_image.save("bg_image", image_content, save=commit)
            _log.debug("Background pic successfully downloaded from %s", url)
            return True
        except Exception, e:
            _log.exception(e)
    return None


def cleanup():
    """Run event cleanups"""
    from event.models import Event, EventTweet
    _log.debug("Started cleanup")
    try:
        dtmax = date.today() - timedelta(days=getattr(settings, 'EVENT_CLEANUP_DAYS_MIN', 14))
        dtmin = date.today() - timedelta(days=getattr(settings, 'EVENT_CLEANUP_DAYS_MAX', 16))
        ex = Event.objects.filter(event_date__gte=dtmin, event_date__lt=dtmax)
        for e in ex:
            d = e.event_date
            # keep only 50 or so tweets per event
            t = list(e.eventtweet_set.values_list("id", flat=True).order_by("-pk")[:60])
            if t:
                last = t[-1]
                e.eventtweet_set.delete_tweets_for_event(event=e, min_pk=last)
                _log.debug("Deleted tweets for event %s",  e.pk)
            else:
                _log.debug("Nothing to delete for event %s" % e.pk)
        _log.debug("Cleanup done")
        count = EventTweet.objects.count()
        _log.info("Tweet cleanup done %s" % count)
    except Exception, e:
        _log.exception(e)


def get_ticketmaster_search_url(querystring):
    '''Return search URL if ticketmaster search returns records.'''
    try:
        querystring = urlencode({'q':querystring})
        url = settings.TICKETMASTER_JSON_SEARCH_URL % querystring
        ret = download_url(url)
        if not ret:
            return None
        results = json.loads(ret)
        response = results.get('response', {})
        nfound = response.get('numFound', 0)
        if nfound:
            url = settings.TICKETMASTER_SEARCH_URL % querystring
        return nfound and url[:750] or None
    except Exception, e:
        _log.warn("TicketMaster verification failed for query: %s\n%s", querystring, e)
        return None

        
def get_feed_signature(user_profile_id, feed_type):
    user_profile_id = str(user_profile_id)
    hash = sha_constructor(settings.SECRET_KEY + user_profile_id.lower() + feed_type).hexdigest()[::2]
    return hash


def get_friends_favorites_count(user_profile, location=None):
    from event.models import Event
    ff = Event.objects.active(attending_user=user_profile).filter(
       recommendedevent__user_profile=user_profile
    ).distinct()
    if settings.RECOMMENDED_EVENTS_FILTER_BY_LOCATION and location:
        ff = ff.filter(location__in=('destination', 'user-entered', location))
    return ff.count()


def do_foursquare_venues(dt=None):
    """Collect foursquare checkin stats for each venue that has events happening today."""
    from fsq import FoursquareApi
    from rdutils.mathutils import farey
    from event.models import Event, Venue, FoursquareTrend
    
    etz = tz.tzstr('EST5EDT') # Eastern timezone
    headers = {
        'User-Agent': getattr(settings, 'FOURSQUARE_USER_AGENT', settings.USER_AGENT)
    }
    fsq = FoursquareApi(headers)
    dt = dt or date.today()
    # Active venues
    events = Event.objects.filter(is_approved=True, event_date=dt).order_by('event_date', 'event_start_time', 'pk')
    venue_ids = set()
    venues = []
    for ev in events:
        if ev.venue.pk not in venue_ids:
            venues.append(ev.venue)
            venue_ids.add(ev.venue.pk)
    previous_venues = Venue.objects.exclude(pk__in=list(venue_ids)).filter(fsq_checkins__gt=0)
    previous_venues.update(fsq_checkins=0, fsq_ratio=u'', fsq_mf=0, fsq_fm=0, fsq_m=0, fsq_f=0)
    # Get and populate FSQ ids of active venues where fsq_id was not previously obtained
    for v in venues:
        if not v.fsq_id and v.geo_loc and ',' in v.geo_loc:            
            keyx = shorten_key(u"venue_id_4sq:%s" % v.pk)            
            vx = cache.cache.get(keyx, None)
            if vx is None:                
                lat, lng = v.geo_loc.split(',')            
                venue_name = v.name.encode("utf-8", "ignore")                
                _log.debug("Getting 4sq venue ID for %s", venue_name)       
                sleep(.25)         
                vx = fsq.get_venues(geolat=lat, geolong=lng, q=venue_name, l=1)                
                try:
                    vid = vx['groups'][0]['venues'][0]['id']
                    v.fsq_id = unicode(vid)
                    v.save()
                except Exception, e:
                    vid = 0
                    _log.debug("FSQ ID for venue %s could not be obtained: %s\n%s", v.pk, e, vx)
                cache.cache.set(keyx, vid, 7200) # cache for 2 hours
    # Get and populate checkin for each venue
    num = 0
    err = 0
    api_cache = {} # save results of calls to a venue during this run so that we don't call for the same venue twice
    for v in venues:
        if v.fsq_id:            
            _log.debug("Fetching details for 4sq venue %s (our venue %s)", v.fsq_id, v.pk)
            key = shorten_key(u"venue_4sq:%s" % v.pk)
            whos_here = cache.cache.get(key, [])            
            fv = api_cache.get(v.fsq_id, None)
            if fv:
                _log.debug("Using cached 4sq venue call")
            try:
                if not fv:
                    sleep(.5)
                fv = fv or fsq.get_venue_detail(vid=v.fsq_id, username=settings.FOURSQUARE_USERNAME, password=settings.FOURSQUARE_PASSWORD)            
            except (URLError, AttributeError):
                sleep(30) # try once more in 30 seconds
                fv = fsq.get_venue_detail(vid=v.fsq_id, username=settings.FOURSQUARE_USERNAME, password=settings.FOURSQUARE_PASSWORD)            
            api_cache[v.fsq_id] = fv # cache it
            if 'ratelimited' in fv:
                _log.error("We've been ratelimited by FSQ")
                err += 1
                return num, err
            num += 1
            try:
                whos_here = []
                v.fsq_checkins = int(fv['venue']['stats']['herenow'])
                if not v.fsq_checkins:
                    _log.debug("No one at venue %s, %s", v.fsq_id, v.name)
                    FoursquareTrend.objects.create(venue=v, fsq_id=v.fsq_id, fsq_checkins=v.fsq_checkins)
                    v.fsq_checkins = 0
                    v.fsq_ratio = u''
                    v.fsq_m = 0
                    v.fsq_f = 0
                    v.fsq_mf = 0
                    v.fsq_fm = 0
                    v.save()
                    continue
                _log.debug("Venue:\n%s", fv)
                male, female = 0, 0
                try:
                    event = v.get_current_event(include_hidden=True)
                    _log.debug("Event %s", event)
                    if event:
                        td = event.timedelta
                    else:
                        td = None 
                    # compute fsq ratio
                    for cx in fv['venue']['checkins']:
                        user = cx['user']
                        userid = user.get('id', u'')
                        checkin_time = cx.get('created', None)          
                        _log.debug("checkin %s, %s", userid, checkin_time)              
                        if event and userid and checkin_time:
                            # store checkins for this venue
                            userid = unicode(userid)
                            checkin_time = dtparser.parse(checkin_time)
                            checkin_time = checkin_time.astimezone(etz)
                            if td:
                                checkin_time = checkin_time - td # converted to event's local timezone
                            user_profiles = list(UserProfile.objects.filter(fsq_userid=userid))
                            for up in user_profiles:
                                checkin, created = event.eventcheckin_set.get_or_create(
                                    fsq_userid=userid,
                                    user_profile=up,
                                    defaults=dict(checkin_time=checkin_time)
                                ) 
                                if not created:
                                    checkin.checkin_time = checkin_time
                                    checkin.save()
                                _log.debug("Checkin saved with user profile %s -> %s", event.pk, userid)
                            if not user_profiles:
                                # record checkin without user profile
                                checkin, created = event.eventcheckin_set.get_or_create(
                                    fsq_userid=userid,
                                    defaults=dict(checkin_time=checkin_time)
                                ) 
                                if not created:
                                    checkin.checkin_time = checkin_time
                                    checkin.save()
                                _log.debug("Checkin saved without user profile %s -> %s", event.pk, userid) 
                        gender, photo_url = user.get('gender', ''), user.get('photo', u'')
                        if photo_url:
                            whos_here.append(photo_url)
                        if gender:
                            gender = gender.lower()
                            if gender == 'male':
                                male += 1
                            elif gender == 'female':
                                female += 1
                    _log.debug("male:female = %s:%s", male, female)
                    if not female:
                        if male:
                            v.fsq_ratio = u"%s:0" % male
                    else: # female > 0
                        if male:
                            if male > female:
                                rx = float(male) / float(female)
                                m, f = farey(rx, 1)
                            elif male == female:
                                m, f = 1, 1
                            else: # male < female
                                rx = float(female) / float(male)
                                f, m = farey(rx, 1)
                            v.fsq_ratio = u"%s:%s" % (m, f)
                        else: # male == 0
                            v.fsq_ratio = u"0:%s" % female
                    _log.debug("ratio = %s", v.fsq_ratio)
                    t = float(male + female)
                    mf = unicode(t and float(male)/t or 0)
                    fm = unicode(t and float(female)/t or 0)
                    v.fsq_m = male
                    v.fsq_f = female
                    v.fsq_mf = mf
                    v.fsq_fm = fm
                    FoursquareTrend.objects.create(
                        venue=v,
                        fsq_id=v.fsq_id,
                        fsq_checkins=v.fsq_checkins,
                        fsq_ratio=v.fsq_ratio,
                        fsq_m=male,
                        fsq_f=female,
                        fsq_mf=mf,
                        fsq_fm=fm
                    )
                except Exception, e:
                    _log.exception(e)
                    _log.warn("FSQ genders for venue %s could not be obtained: %s\n%s", v.pk, e, fv)                                
            except Exception, e:
                _log.warn("FSQ checkins for venue %s could not be obtained: %s\n%s", v.pk, e, fv)
                # v.fsq_checkins = 0
                err += 1
            cache.cache.set(key, whos_here, 3800)
            v.save()
    return num, err

    