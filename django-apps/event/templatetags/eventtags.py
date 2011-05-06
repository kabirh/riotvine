import logging
import random
from datetime import date, datetime, timedelta
import time

from django import template
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.comments.models import Comment
from django.utils.encoding import iri_to_uri
from django.utils.http import urlencode

from rdutils.cache import key_suffix, short_key, clear_keys, cache
from twitter.utils import get_tweets_by_hashtag, convert_timestamp
from artist.models import ArtistProfile
from photo.models import PhotoSize, PhotoVersion
from event import exceptions


_log = logging.getLogger("event.templatetags.eventtags")

register = template.Library()


@register.inclusion_tag("event/tags/who_is_interested.html", takes_context=True)
def event_interested_users(context, event, user_profile=None, limit="9"):
    ctx = {}
    try:
        limit = int(limit)
    except ValueError:
        limit = 9
    ctx['limit'] = limit
    sfx = key_suffix('attendees', event.pk)
    key = u"city-interested:%s:%s" % (sfx, limit)
    interested = cache.cache.get(key, None)
    if interested is None:
        interested = event.get_interested(limit=limit, order_by="?")
        # TODO: give preference to logged in user's friends    
        cache.cache.set(key, interested, 600)
    ctx['interested'] = interested
    ctx['show_more'] = len(ctx['interested']) >= limit
    ctx['MEDIA_URL'] = context['MEDIA_URL']
    request = context.get('request', None)
    if request:
        ctx['mobile'] = request.mobile
    ctx['e'] = event
    return ctx


@register.inclusion_tag("event/tags/photo_thumbnails.html")
def event_photo_thumbnails(event, aspect="thumbnail", title="Event photos", limit=None):
    size = PhotoSize.objects.get_thumbnail(cropped=aspect.lower()=='square')
    photos = PhotoVersion.objects.get_for_object(event, size=size).order_by("?")
    if limit:
        photos = photos[:int(limit)]
    return {'event':event, 'photos':photos, 'aspect':aspect.title(), 'title':title}


@register.simple_tag
def event_error_message(exception_class_name):
    """DRY: Return event error message from event.exceptions.*Error"""
    try:
        instance = getattr(exceptions, exception_class_name)()
        return instance.message
    except AttributeError, e:
        if settings.DEV_MODE:
            assert False # Show debugging info on screen in development mode.
        return u''


@register.inclusion_tag("event/tags/summary.html", takes_context=True)
def event_summary(context, event, classes='', is_owner=False, is_admin=False, include_title=False, show_detail_link=False, separate_description=False, changes=False):
    request = context['request']
    event.is_attending = request.user_profile and request.user_profile.pk in event.attendeeset
    ctx = {
            'e':event, 'event':event, 'classes':classes, 'is_owner':is_owner,
            'is_admin':is_admin, 'include_title':include_title,
            'show_detail_link':show_detail_link,
            'separate_description':separate_description,
            'changes':changes,
            'context':context,
            'TWITTER_SHARER':context['TWITTER_SHARER'],
            'MEDIA_URL':context['MEDIA_URL'],
            'request':request,
            'user':context['user'],
    }
    return ctx


def _event_badge(event, badge_type='i'):
    from event.models import Badge
    ctx = {'event':event}
    try:
        badge = event.badge_set.get(badge_type=badge_type)
        ctx['badge'] = badge
    except Badge.DoesNotExist:
        pass
    return ctx


@register.inclusion_tag("event/tags/badge_external_code.html")
def event_external_badge_code(event):
    if not event.is_public:
        return {}
    ctx = _event_badge(event, badge_type='e')
    return ctx


@register.inclusion_tag("event/tags/badge_internal.html")
def event_badge_internal(event, classes='', is_owner=False, is_admin=False):
    ctx = _event_badge(event, badge_type='i')
    ctx['classes'] = classes
    ctx['is_owner'] = is_owner
    if is_owner or is_admin:
        # Show uncached badge to admin or event owner
        ctx['query_string'] = "?q=%s" % random.randint(1000, 1000000)
    return ctx


@register.inclusion_tag("event/tags/badge_external.html")
def event_badge_external(event, classes='', show_code=False, title='', is_owner=False, is_admin=False):
    if not event.is_public:
        return {}
    ctx = _event_badge(event, badge_type='e')
    ctx['classes'] = classes
    ctx['show_code'] = show_code == 'show_code'
    ctx['title'] = title
    ctx['is_owner'] = is_owner
    if is_owner or is_admin:
        # Show uncached badge to admin or event owner
        ctx['query_string'] = "?q=%s" % random.randint(1000, 1000000)
    return ctx


@register.inclusion_tag("event/tags/blurb_list.html")
def event_blurbs_latest(max_num="10"):
    from event.models import Event
    max_num = int(max_num)
    events = Event.objects.active().order_by('-approved_on', '-event_date')[:max_num]
    ctx = {'max_num':max_num, 'events':events}
    return ctx


@register.inclusion_tag("event/tags/attendee_list.html", takes_context=True)
def event_attendees_latest(context, max_num="10"):
    from event.models import Attendee
    max_num = int(max_num)
    attendees = Attendee.objects.select_related('attendee', 'attendee_profile', 'event').filter(amount__gt=0).order_by('-paid_on')[:max_num]
    ctx = {'max_num':max_num, 'attendees':attendees, 'context':context}
    return ctx


@register.inclusion_tag("event/tags/event_attendees.html", takes_context=True)
def event_attendees(context, event, max_num="8"):
    max_num = int(max_num)
    n = event.attendee_set.all().count()
    attendees = event.attendee_set.select_related('attendee', 'attendee_profile').order_by('?')[:max_num]
    ctx = {'max_num':max_num, 'attendees':attendees, 'context':context, 'event':event, 'n':n}
    return ctx


def _get_artist(user):
    """Return an ``ArtistProfile`` instance for ``user``.

    ``user`` may be a ``User`` instance or a ``User.username``.

    """
    if not isinstance(user, ArtistProfile):
        if isinstance(user, User):
            artist = user.get_profile().artist
        else:
            artist = ArtistProfile.objects.get(user_profile__user__username=user)
    else:
        artist = user
    return artist


def _apply_limit(events, limit):
    """Internal DRY helper"""
    total_count = events.count()
    has_more = False
    if limit:
        limit = int(limit)
        events = events[:limit]
        has_more = total_count > limit
    return {'events':events, 'has_more':has_more, 'total_count':total_count}


@register.inclusion_tag("event/tags/admin_list.html")
def events_active(artist, title='Active shows', limit="3"):
    """Render active events; user may be a username, a User instance or an ArtistProfile instance."""
    artist = _get_artist(artist)
    events = artist.event_set.active().order_by('event_date')
    ctx = {'title':title, 'event_type':'active'}
    ctx.update(_apply_limit(events, limit))
    return ctx


@register.inclusion_tag("event/tags/admin_list.html")
def events_approved_upcoming(artist, title='Upcoming shows', limit="3"):
    """Render approved events that are starting in the future; user may be a username, a User instance or an ArtistProfile instance."""
    artist = _get_artist(artist)
    events = artist.event_set.visible(is_approved=True, event_date__gt=date.today()).order_by('event_date')
    total_count = events.count()
    ctx = {'title':title, 'event_type':'approved-upcoming'}
    ctx.update(_apply_limit(events, limit))
    return ctx


@register.inclusion_tag("event/tags/admin_list.html")
def events_unsubmitted(artist, title='Unsubmitted shows', limit="3"):
    """Render events not yet submitted; user may be a username, a User instance or an ArtistProfile instance."""
    artist = _get_artist(artist)
    events = artist.event_set.visible(is_submitted=False).order_by('event_date')
    ctx = {'title':title, 'event_type':'unsubmitted'}
    ctx.update(_apply_limit(events, limit))
    return ctx


@register.inclusion_tag("event/tags/admin_list.html")
def events_pending_approval(artist, title='Shows pending approval', limit="3"):
    """Render events pending approval; user may be a username, a User instance or an ArtistProfile instance."""
    artist = _get_artist(artist)
    events = artist.event_set.visible(is_approved=False, is_submitted=True).order_by('event_date')
    ctx = {'title':title, 'event_type':'pending-approval'}
    ctx.update(_apply_limit(events, limit))
    return ctx


@register.inclusion_tag("event/tags/admin_list.html")
def events_expired(artist, title='Past shows', limit="3"):
    """Render past events; user may be a username, a User instance or an ArtistProfile instance."""
    artist = _get_artist(artist)
    events = artist.event_set.visible(is_approved=True, event_date__lt=date.today()).order_by('-event_date')
    ctx = {'title':title, 'event_type':'expired'}
    ctx.update(_apply_limit(events, limit))
    return ctx


def comment_sorter(c):
    """Given a JSON format tweet or a Django Comment instance, return the posted date"""
    if hasattr(c, 'submit_date'):
        return c.submit_date # Django comment
    if hasattr(c, 'added_on'):
        return c.added_on # Event tweet
    else: # Regular tweet
        return convert_timestamp(c['created_at'], c)


@register.inclusion_tag("event/tags/comments.html", takes_context=True)
def event_comments(context, event, name='comments'):
    """Add event comments and tweets to the context under the given name"""
    comments = list(Comment.objects.for_model(event).select_related('user').order_by('-submit_date'))
    limit = event.max_tweets or settings.EVENT_MAX_TWEETS
    tweets = event.eventtweet_set.tweets(is_retweet=True, limit=limit)
    if tweets:
        comments.extend(tweets)
        comments.sort(key=comment_sorter, reverse=True)
    context[name] = comments
    return {}


@register.inclusion_tag("event/event_calendar.html")
def event_user_calendar(user_profile):
    from event.models import Event
    events = Event.objects.active().filter(
        attendee__attendee_profile=user_profile
    ).distinct().order_by('event_date', 'event_start_time')[:25]
    return {'events':events}


@register.simple_tag
def event_friends(event, user_profile):
    ekey = key_suffix('attendees', event.pk)
    ukey = key_suffix('friends', user_profile.pk)
    key = short_key(u"event_friends:%s:%s" % (ekey, ukey))
    value = cache.cache.get(key, None)
    if value is None:
        value = ""
        friends = user_profile.friendset
        if friends:
            attendees = event.attendeeset
            fr_at = friends & attendees # friends who are also attendees of this event
            if fr_at:
                n = len(fr_at)
                if n == 1:
                    value = "| 1 Friend"
                else:
                    value = u"| %d Friends" % n
        cache.cache.set(key, value)
    return value


@register.inclusion_tag("event/tags/amazon_mp3_player.html")
def event_amazon_mp3_player(event):
    ctx = {
        'e':event,
        'asins':event.aws_asins,
        'associate_tag':settings.AWS_ASSOCIATE_TAG,
    }
    return ctx


@register.simple_tag
def gcal_url(event):
    gcal_url = settings.GCAL_ADD_EVENT_URL
    gcal_params = event.get_gcal_params()
    return iri_to_uri(gcal_url + "?" + urlencode(gcal_params) + "&sprop=name:%s" % settings.UI_SETTINGS['UI_SITE_TITLE'])


@register.inclusion_tag("event/tags/dynamic_badge_code.html")
def event_dynamic_badge(event):
    domain = settings.DISPLAY_SITE_DOMAIN
    showdomain = False
    if settings.DEV_MODE and getattr(settings, 'SUBDOMAIN_PORT', ''):
        domain = settings.DEV_SITE_DOMAIN + ':' + settings.SUBDOMAIN_PORT
        showdomain = True
    ctx = {
        'e':event,
        'event':event,
        'domain':domain,
        'showdomain':showdomain,
        'MEDIA_URL':settings.MEDIA_URL,
        'version':settings.BADGE_VERSION,
        'badgetype':settings.BADGE_CODE_TYPE,
    }
    return ctx

