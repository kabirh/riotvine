"""

Middleware classes to grab a site visitor's zip code.

"""
import logging
import time
import os
import urllib

from django.conf import settings
from django.utils.http import cookie_date
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect

from event.geoip import RiotVineGeoIP
from registration.models import UserProfile


_log = logging.getLogger('event.middleware')

_SUBDOMAIN_PORT = getattr(settings, 'SUBDOMAIN_PORT', '')
if _SUBDOMAIN_PORT:
    _SUBDOMAIN_PORT = u":" + _SUBDOMAIN_PORT


class AnonymousEventMiddleware(object):
    """Add anonymous user's favorited event to her calendar when she logs in.

    The frontend sets a cookie named "addevent" containing the add_to_calendar URL. 
    Use this cookie to deduce the event.

    """
    def process_request(self, request):
        if request.user.is_authenticated():
            # if this user has an addevent cookie, 
            # add the event to the user's calendar and remove the cookie.
            event_id = request.COOKIES.get("addevent", None)
            if event_id:
                event_id = urllib.unquote(event_id)
                from event.views import add_to_calendar
                try:
                    event_id = event_id.split('/')[-2].strip()
                    add_to_calendar(request, event_id, force=True)
                    _log.debug("Event %s added to user %s's calendar", event_id, request.user.pk)
                except Exception, e:
                    _log.warn("Could not add event %s to user %s's calendar", event_id, request.user.pk)
                    _log.exception(e)
                request.removeevent = True
        return None
                
    def process_response(self, request, response):
        """Set location cookie."""
        if getattr(request, 'removeevent', False):
            response.delete_cookie("addevent", domain=settings.SESSION_COOKIE_DOMAIN)
        return response


class LocationMiddleware(object):
    def process_request(self, request):
        """Populate the visitor's location slug in `request.location`.

        1. lookup the host from the HTTP_HOST env var.
        2. lookup the location in a cookie.
        3. derive it using the GeoIP API.

        Also set the request attribute `location_source`
        to indicate the source of this location value (i.e. cookie, geoip, or implicit.)

        """
        request.location = None
        request.location_source = u'cookie' # default
        location = None
        http_host = request.get_host()
        #_log.debug("HTTP host: %s" % http_host)
        if http_host:
            cx = http_host.lower().split(".")
            if len(cx) > 2:
                subdomain = cx[0]
                if subdomain in settings.LOCATION_SUBDOMAIN_MAP:
                    subdomain = settings.LOCATION_SUBDOMAIN_MAP[subdomain]
                if subdomain in settings.LOCATION_DATA.keys():
                    location = subdomain.lower()
                    request.location_source = u'subdomain'
        if not location:
            location = request.COOKIES.get(settings.LOCATION_COOKIE_NAME, '').lower()
            if location not in settings.LOCATION_DATA.keys():
                if 'HTTP_X_FORWARDED_FOR' in request.META:
                    ip_addr = request.META['HTTP_X_FORWARDED_FOR']
                else:
                    ip_addr = request.META['REMOTE_ADDR']
                # Location was not found in the cookie. 
                # Look it up via GeoIP
                geoip = RiotVineGeoIP()
                location = geoip.nearest_location(ip_addr)
                request.location_source = u'geoip'
        request.location = location
        request.location_name = settings.LOCATION_DATA.get(location)[3]
        other_cities = sorted(settings.LOCATION_DATA.keys())
        other_cities.remove(location)
        request.other_cities =  ' /  '.join([
            ('<a href="http://%s.%s%s%s">%s</a>' % (settings.LOCATION_SUBDOMAIN_REVERSE_MAP[loc], settings.DISPLAY_SITE_DOMAIN,  _SUBDOMAIN_PORT, reverse("list_events"), settings.LOCATION_DATA.get(loc)[3])) for loc in other_cities
        ])
        return None

    def process_response(self, request, response):
        """Set location cookie."""
        location = getattr(request, 'location', None)
        if location:
            max_age = settings.LOCATION_COOKIE_AGE_SECONDS
            expires_time = time.time() + max_age
            expires = cookie_date(expires_time)
            response.set_cookie(settings.LOCATION_COOKIE_NAME, location, max_age=max_age, expires=expires, domain=settings.SESSION_COOKIE_DOMAIN)
        return response

