"""

Event AMQP tasks

from event.amqp.tasks import *
from registration.models import UserProfile
user_profile = UserProfile.objects.get(user__username='fan1')
build_recommended_events(user_profile.pk)

"""
import logging
import time
from datetime import date, timedelta, datetime
from datetime import time as timex
from uuid import uuid4

from django.conf import settings
from django.template.defaultfilters import date as date_filter
from django.template.defaultfilters import time as time_filter
from django.db.models import Q
from django.db import connection, transaction

from amqp import DataStorage, aq
from twitter.amqp.queues import SearchQ
from twitter.amqp.tasks import search as twitter_search
from twitter.utils import hashtags_to_q_list
from event.amqp.queues import EventsQ
from rdutils.cache import shorten_key
from registration.models import Friendship, Follower


_log = logging.getLogger('event.amqp.tasks')
_DELIVERY_MODE = getattr(settings, 'AMQP_DELIVERY_MODE', 1)


def build_recommended_events(user_profile_id, queue=None):
    """Refresh recommended events for the given user"""
    try:
        kx = uuid4().hex
        msg = aq.Message(
            '',
            delivery_mode=_DELIVERY_MODE,
            correlation_id=shorten_key('rec_events:%s:%s' % (user_profile_id, kx)),
            application_headers={'user_profile_id':user_profile_id},
        )
        q = queue or EventsQ(bind_queue=False)
        q.send(msg, q.exchange_name, 'signal.events.build_recommended_events')
        _log.debug("Recommended events builder initiated for user %s", user_profile_id)
    except Exception, e:
        _log.debug("Could not build recommended events for user %s", user_profile_id)
        _log.exception(e)


def recommend_event_to_friends(user_profile_id, event_id, queue=None):
    """Recommend an event to user's friends"""
    try:
        kx = uuid4().hex
        msg = aq.Message(
            '',
            delivery_mode=_DELIVERY_MODE,
            correlation_id=shorten_key('rec_event:%s:%s:%s' % (user_profile_id, event_id, kx)),
            application_headers={'user_profile_id':user_profile_id, 'event_id':event_id},
        )
        q = queue or EventsQ(bind_queue=False)
        q.send(msg, q.exchange_name, 'signal.events.recommend_event_to_friends')
        _log.debug("Recommending event %s to user %s's friends", event_id, user_profile_id)
    except Exception, e:
        _log.debug("Could not recommend event %s to user %s's friends", event_id, user_profile_id)
        _log.exception(e)


def build_recommendations(queue=None):
    q = queue or EventsQ(bind_queue=False)
    now = date.today()
    users = Friendship.objects.filter(
        user_profile2__attendee__event__is_deleted=False,
        user_profile2__attendee__event__is_approved=True,
        user_profile2__attendee__event__event_date__gte=now
    ).distinct().values_list('user_profile1_id', flat=True)
    users = list(users)
    users2 = list(Follower.objects.distinct().values_list('follower_id', flat=True))
    users = set(users + users2)
    for user_profile_id in users:
        build_recommended_events(user_profile_id, q)


def send_event_reminder(reminder_dict, queue=None, email_type='reminder'):
    """Send upcoming event reminders to a user"""
    try:
        user_profile_id = reminder_dict['attendee_profile_id']
        msg = aq.Message(
            reminder_dict,
            content_type='application/json',
            delivery_mode=_DELIVERY_MODE,
            application_headers={},
        )
        q = queue or EventsQ(bind_queue=False)
        q.send(msg, q.exchange_name, 'signal.events.send_event_reminder')
        _log.debug("Event %s initiated for user %s", email_type, user_profile_id)
    except Exception, e:
        _log.debug("Could not send event %s to user %s", email_type, user_profile_id)
        _log.exception(e)


def send_hourly_reminders(hours=1):
    tz_locs = {}
    for key, value in settings.LOCATION_DATA.iteritems():
        tz = value[4]
        loc_list = tz_locs.setdefault(tz, [])
        loc_list.append(key)
    tz_locs['ET'].extend(['user-defined', 'destination'])
    _log.debug("TZ Locations %s", tz_locs)
    et = datetime.now()
    ct = datetime.now() - timedelta(hours=1)
    pt = datetime.now() - timedelta(hours=3)
    send_reminders(hours=hours, location_list=tz_locs['ET'], current_time=et)
    send_reminders(hours=hours, location_list=tz_locs['CT'], current_time=ct)
    send_reminders(hours=hours, location_list=tz_locs['PT'], current_time=pt)


def send_reminders(hours=32, queue=None, limit_to_username=None, location_list=None, current_time=None):
    from event.models import Attendee, Event
    from event.templatetags.eventtags import event_friends
    aq = Attendee.objects.select_related('event__artist', 'event__venue', 'attendee', 'attendee_profile__user')
    if hours < 24:
        now = current_time or datetime.now()
        today = now.date()
        next_hour = now + timedelta(hours=hours+1)
        next_hour2 = next_hour + timedelta(hours=1)        
        if next_hour2.hour < next_hour.hour:
            return # don't send reminders around midnight for now
        min_time = timex(hour=next_hour.hour)
        max_time=timex(hour=next_hour2.hour)
        _log.debug("Hourly %s, %s", min_time, max_time)
        if location_list:
            _log.debug("Locations: %s", location_list)
            evlist = aq.filter(
                event__is_deleted=False,
                event__is_approved=True,
                event__event_date=today,
                event__event_start_time__gte=min_time,
                event__event_start_time__lt=max_time,
                event__location__in=location_list,
                attendee__is_active=True,
                attendee_profile__send_reminders=True
            )
        else:
            evlist = aq.filter(
                event__is_deleted=False,
                event__is_approved=True,
                event__event_date=today,
                event__event_start_time__gte=min_time,
                event__event_start_time__lt=max_time,
                attendee__is_active=True,
                attendee_profile__send_reminders=True
            )        
    else :
        now = date.today()
        end_date = date.today() + timedelta(hours=hours)    
        evlist = aq.filter(
            event__is_deleted=False,
            event__is_approved=True,
            event__event_date__gte=now,
            event__event_date__lte=end_date,
            attendee__is_active=True,
            attendee_profile__send_reminders=True
        )
    evlist = evlist.order_by('event__event_date')
    if limit_to_username:
        evlist = evlist.filter(attendee__username=limit_to_username)
    num = evlist.count()
    if not num:
        return
    _log.debug("Reminding people about %s events coming up in the next %s hours", num, hours)
    q = queue or EventsQ(bind_queue=False)
    for o in evlist:
        e = o.event
        v = e.venue
        a = o.attendee
        p = o.attendee_profile
        d = dict(
            email_type='reminder',
            event_id=e.pk,
            event__title=e.title,
            event__event_url=e.get_absolute_url(force_hostname=True),
            event__tweet_count=e.tweet_count,
            event__short_url=e.get_short_url(),
            event__ticket_url=e.ticket_or_tm_url,
            event__event_date=e.event_date,
            event__event_start_time=e.event_start_time,
            event__event_timezone=e.event_timezone,
            event__venue__name=v.name,
            event__venue__address=v.address,
            event__venue__citystatezip=v.citystatezip,
            event__venue__map_url=v.map_url,
            attendee__username=a.username,
            attendee__email=a.email,
            attendee__first_name=a.first_name,
            attendee__last_name=a.last_name,
            attendee_profile_id=p.pk,
        )
        if hours < 2 and e.show_checkins:
            d['fsq_checkins'] = v.fsq_checkins
            d['fsq_ratio'] = v.fsq_ratio_display
        num_fr = event_friends(e, p).lower().replace('|', '')
        if num_fr.endswith("friend"):
            num_fr = num_fr + " is in for this event"
        elif num_fr.endswith("friends"):
            num_fr = num_fr + " are in for this event"
        d['num_friends'] = num_fr
        d['event__event_date'] = date_filter(d['event__event_date'], "l, N j, Y")
        if d['event__event_start_time']:
            d['event__event_start_time'] = time_filter(d['event__event_start_time'])
        # add ripe picks:
        # TODO: cache ripe picks for a few minutes
        picks = Event.objects.active().select_related('artist').filter(
            recommendedevent__user_profile=p
        ).distinct().order_by('event_date')
        if picks:
            ripe_picks = []
            d['ripe_picks'] = ripe_picks
            for rp in picks:
                ripe = dict(
                    event__event_url=rp.get_absolute_url(force_hostname=True),
                    event__title=rp.title,
                    event__event_date=date_filter(rp.event_date, "l, N j, Y"),
                    event__event_start_time=time_filter(rp.event_start_time),
                    event__event_timezone=rp.event_timezone,
                )
                ripe_picks.append(ripe)
                num_fr = event_friends(rp, p).lower().replace('| ', '')
                if num_fr.endswith("friend"):
                    num_fr = "<b>" + num_fr + "</b> is interested in"
                elif num_fr.endswith("friends"):
                    num_fr = "<b>" + num_fr + "</b> are interested in"
                ripe['num_friends'] = num_fr
        send_event_reminder(d, queue=q)


def send_favorites(hours=25, queue=None, limit_to_username=None):
    from event.models import RecommendedEvent, Event
    from event.templatetags.eventtags import event_friends
    from registration.models import UserProfile
    now = date.today()
    add_date_threshold = date.today() - timedelta(hours=hours)
    profiles = UserProfile.objects.active().filter(send_favorites=True).order_by('pk')
    if limit_to_username:
        profiles = profiles.filter(user__username=limit_to_username)
    n = 0
    q = queue or EventsQ(bind_queue=False)
    for p in profiles:
        a = p.user
        d = dict(
            email_type='favorites',
            attendee__username=a.username,
            attendee__email=a.email,
            attendee__first_name=a.first_name,
            attendee__last_name=a.last_name,
            attendee_profile_id=p.pk
        )
        picks = Event.objects.active().select_related('artist').filter(
                recommendedevent__user_profile=p,
                recommendedevent__added_on__gte=add_date_threshold,
        ).distinct().order_by('event_date', 'event_start_time')
        if picks:
            ripe_picks = []
            d['ripe_picks'] = ripe_picks
            for rp in picks:
                ripe = dict(
                    event__event_url=rp.get_absolute_url(force_hostname=True),
                    event__title=rp.title,
                    event__event_date=date_filter(rp.event_date, "l, N j, Y"),
                    event__event_start_time=time_filter(rp.event_start_time),
                    event__event_timezone=rp.event_timezone,
                )
                ripe_picks.append(ripe)
                num_fr = event_friends(rp, p).lower().replace('| ', '')
                if num_fr.endswith("friend"):
                    num_fr = "<b>" + num_fr + "</b> is interested in"
                elif num_fr.endswith("friends"):
                    num_fr = "<b>" + num_fr + "</b> are interested in"
                ripe['num_friends'] = num_fr
            send_event_reminder(d, queue=q, email_type='favorites')
            n += 1
    _log.debug("%s event favorite emails sent", n)


def fetch_event_tweets(event, do_reset=False, queue=None, reply_to='signal/signal.events.save_event_tweets', params=None, high_priority=False):
    """Fetch fresh tweets for an event.

    If do_reset is True, first clear all existing tweets.

from event.models import *
from event.amqp.tasks import *
f = fetch_event_tweets
ex = Event.objects.get(pk=651)
f(ex)

    """
    from event.models import Event
    if do_reset:
        if event.tweet_count < 5000:
            event.eventtweet_set.delete_tweets_for_event(event)
            event.tweet_count = event.eventtweet_set.count()
            super(Event, event).save()
            do_reset = False
            _log.warn("Reset tweets for event %s", event.pk)
        else:
            event.tweet_count = 999
            super(Event, event).save()
            transaction.commit_unless_managed()
            _log.warn("Deferred tweet reset for event %s", event.pk)
    if not event.hashtags:
        return # nothing to search
    queue = queue or SearchQ(bind_queue=False)
    params = params or {}    
    params['object_type'] = 'event'
    params['object_id'] = unicode(event.pk)    
    maxlength = 139
    since_id = 0 # event.eventtweet_set.max_tweet_id()
    if since_id:
        # params['since_id'] = since_id
        params['since'] = date.today().strftime("%Y-%m-%d")
        maxlength = maxlength - 16
    if settings.TWITTER_GEOIP_ENABLED and 'geocode' not in params:
        # add geoip search params
        locdata = settings.LOCATION_DATA.get(event.location, None)
        if locdata:
            params['geocode'] = u"%s,%s,%s" % (locdata[0], locdata[1], settings.TWITTER_SEARCH_DISTANCE)
    if settings.TWITTER_GEOIP_ENABLED and 'geocode' in params:
        maxlength = maxlength - 40
    qlist = hashtags_to_q_list(event.hashtags, maxlength=maxlength)    
    first = True
    for q in qlist:
        params['q'] = q
        if not first:
            do_reset = False
        twitter_search(event.pk, params, object_type='event', reply_to=reply_to, queue=queue, extra_headers={'do_reset':do_reset}, high_priority=high_priority)
        first = False
    try:
        del params['geocode']
    except KeyError:
        pass


def fetch_all_event_tweets(queue=None, params=None, events=None):
    from event.models import Event
    params = params or {}
    queue = queue or SearchQ(bind_queue=False)
    if events is None:
        events = Event.objects.active().order_by('-pk')
    n = events.count()
    npend = queue.get_pending_count()
    if npend > 5*n:
        queue.purge() # clear large backlog of searches
    for e in events:
        fetch_event_tweets(e, queue=queue, params=params)
    _log.warn("Issued %s event tweet searches", n)


def fetch_current_event_tweets(queue=None, params=None):
    """Fetch Tweets for events happening in the next 14 days and all destination events"""
    from event.models import Event
    threshold = date.today() + timedelta(days=14)
    ex = Event.objects.active().filter(
        Q(event_date__lte=threshold) |
        Q(location='destination')
    ).order_by('event_date')
    fetch_all_event_tweets(queue=queue, params=params, events=ex)


def event_created(event, queue=None):
    """Send out an event-created signal to the queue of listeners interested in it"""
    try:
        event.eventcreatedsignal_set.get_or_create()
    except Exception, e:
        _log.exception(e)
        # silently ignore if signal record creation goes wrong    
