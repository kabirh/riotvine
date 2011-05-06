import logging
from urlparse import urlparse

from django.core.cache import cache
from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect
from django.core.urlresolvers import reverse

from common.models import get_and_delete_messages
from rdutils.render import render_view
from photo.models import PhotoSize, PhotoVersion
from campaign.models import Campaign
from registration.models import Friendship
from event.models import Event
from event.utils import get_friends_favorites_count


_log = logging.getLogger('website.views')

_SUBDOMAIN_PORT = getattr(settings, 'SUBDOMAIN_PORT', '')
if _SUBDOMAIN_PORT:
    _SUBDOMAIN_PORT = u":" + _SUBDOMAIN_PORT


def test(request):
    """Health check"""
    return HttpResponse("OK", mimetype='text/plain')


def homepage(request, location=None, template='website/homepage.html'):
    """Landing page view"""
    # If user is logged in and has not asked for the landing page explicitly, 
    # send her to the city page. If an HTTP referer of riotvine.com is present,
    # assume that the user asked for the landing page. Otherwise, she hasn't.
    ctx = {}
    location = location or request.location
    if request.mobile:
        auth_token = request.GET.get('auth_token', None)
        if auth_token:
            # we just got a Facebook login; redirect to fb login view
            fb_login = u"%s?auth_token=%s" % (reverse("fb_login_mobile"), auth_token)
            return HttpResponseRedirect(fb_login)
        template = 'mobile/website/homepage.html'
        _cities = sorted(settings.LOCATION_DATA.keys())
        if _SUBDOMAIN_PORT:
            _cities =  [
                ('<a href="/event/list-by-loc/%s/">%s<span class="arrow">&nbsp;&raquo;</span></a>' % (loc, settings.LOCATION_DATA.get(loc)[3])) for loc in _cities
            ]
        else:
            _cities =  [
                ('<a href="http://%s.%s%s%s">%s<span class="arrow">&nbsp;&raquo;</span></a>' % (settings.LOCATION_SUBDOMAIN_REVERSE_MAP[loc], settings.DISPLAY_SITE_DOMAIN,  _SUBDOMAIN_PORT, reverse("list_events"), settings.LOCATION_DATA.get(loc)[3])) for loc in _cities
            ]
        mobile_homepage_cities = getattr(settings, 'MOBILE_HOMEPAGE_CITIES', None)
        if mobile_homepage_cities:
            cities = mobile_homepage_cities + _cities
        else:
            cities = _cities            
        ctx['cities'] = cities
        if request.user.is_authenticated() and request.REQUEST.get('show_friends', False):
            friends = Friendship.objects.get_friendships(request.user_profile).order_by("-pk")
            ctx['num_friends'] = friends.count()
            ctx['friends'] = friends[:10]
        if request.user.is_authenticated():
            # Get Friends' Favorites count
            ctx['num_ff'] = get_friends_favorites_count(request.user_profile, location)
        return render_view(request, template, ctx)
    if request.user.is_authenticated():
        referer = request.META.get('HTTP_REFERER', None)
        if not referer:
            return HttpResponseRedirect(reverse("list_events"))
        netloc = urlparse(referer.lower()).netloc
        if netloc:
            if settings.DEV_MODE:
                if settings.DEV_SITE_DOMAIN not in netloc:
                    return HttpResponseRedirect(reverse("list_events"))
            elif settings.DISPLAY_SITE_DOMAIN not in netloc:
                return HttpResponseRedirect(reverse("list_events"))   
    for loc, name in settings.LOCATIONS:
        if loc == 'destination':
            continue
        cx = {'top_event_%s' % loc:None, 'top3_events_%s' % loc:[]}
        key = u'rv-top-events_%s' % loc
        if request.user.is_authenticated() and request.user.is_staff:
            # No caching for staff users
            top_events = None
        else:
            top_events = cache.get(key, None)
        if top_events is None:
            ex = list(Event.objects.active_by_location(location=loc, is_homepage_worthy=True).order_by('event_date', 'event_start_time')[:4])
            cache.set(key, ex, int(settings.UI_SETTINGS['UI_CACHE_TIMEOUT']))
        else:
            ex = top_events
        if ex:
            cx['top_event_%s' % loc] = ex[0]
        if len(ex) > 1:
            cx['top3_events_%s' % loc] = ex[1:4]
        ctx.update(cx)
    ctx['next'] = reverse("list_events")
    return render_view(request, template, ctx)


def old_homepage(request, template='website/homepage.html'):
    ctx = {}
    # Merge event and campaign badges by their homepage worthiness date.
    key = u'ir-top3-boxes'
    if request.user.is_authenticated() and request.user.is_staff:
        # No caching for staff users
        top3_objects = None
    else:
        top3_objects = cache.get(key, None)
    if top3_objects is None:
        cx = list(Campaign.objects.active(is_homepage_worthy=True).order_by('-homepage_worthy_on')[:15])
        ex = list(Event.objects.active(is_homepage_worthy=True).order_by('-homepage_worthy_on')[:15])
        mx = ex + cx
        mx.sort(key=lambda x:x.homepage_worthy_on, reverse=True)
        top3_objects = mx[:3]
        cache.set(key, top3_objects, int(settings.UI_SETTINGS['UI_CACHE_TIMEOUT']))
    ctx['top3'] = top3_objects

    # Save top3 object ids so we can exclude them from the mixed feed later
    top3_campaigns = []
    top3_events = []
    for o in top3_objects:
        if hasattr(o, 'venue'):
            top3_events.append(o.pk)
        else:
            top3_campaigns.append(o.pk)

    # Merge 10 event and campaign objects.
    key = u'ir-hp-mixedfeed'
    if request.user.is_authenticated() and request.user.is_staff:
        # No caching for staff users
        mixed_feed = None
    else:
        mixed_feed = cache.get(key, None)
    if mixed_feed is None:
        # Exclude campaigns and events already shown in `top3` above
        c2x = list(Campaign.objects.active().exclude(pk__in=top3_campaigns).order_by('end_date')[:25])
        e2x = list(Event.objects.active().exclude(pk__in=top3_events).order_by('event_date')[:25])
        m2x = e2x + c2x
        m2x.sort(key=lambda x:x.sort_date, reverse=False)
        mixed_feed = m2x[:10]
        cache.set(key, mixed_feed, int(settings.UI_SETTINGS['UI_CACHE_TIMEOUT']))
    ctx['mixed_feed'] = mixed_feed

    size = PhotoSize.objects.get_thumbnail(cropped=True)
    photos = PhotoVersion.objects.select_related('photo').filter(size=size).order_by("-updated_on")[:16]
    ctx['photos'] = photos

    if request.user.is_authenticated():
        ctx['special_messages'] = get_and_delete_messages(request.user, 1)
    return render_view(request, template, ctx)


