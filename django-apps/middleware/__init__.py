import logging
import threading

from django.conf import settings
from django.core.urlresolvers import reverse
from django.contrib.auth import logout
from django.http import HttpResponsePermanentRedirect, HttpResponseRedirect

from rdutils.query import get_or_none
from registration.models import UserProfile, PendingFriendship


_log = logging.getLogger('middleware.init')


class UserProfileMiddleware(object):
    def process_request(self, request):
        if request.user.is_authenticated():
            request.user_profile = get_or_none(UserProfile.objects.active(), user=request.user.pk)
            if request.user_profile:
                pending_friendship_requests = PendingFriendship.objects.filter(
                    invitee_profile__pk=request.user_profile.pk
                ).count()
                request.pending_friendship_requests = pending_friendship_requests
            else:                
                logout(request)
                return HttpResponseRedirect(reverse("home"))
        else:
            request.user_profile = None
            request.pending_friendship_requests = 0


class ThreadNameMiddleware(object):
    """Set the name of the current thread to the logged in username or ANON."""
    def process_request(self, request):
        current_thread = threading.currentThread()
        if request.user.is_authenticated():
            thread_name = request.user.username
        else:
            thread_name = 'ANON'
        current_thread.setName(thread_name)
        return None


class ProxyMiddleware(object):
    """Middleware for Django running behind a reverse proxy. 

    Set the request's address from the X-Forwarded-For header,
    and set is_secure() according to the X-Forwarded-Proto header.

    """
    def process_request(self, request):
        if not settings.PROXY_ENABLED:
            return None
        if 'https' in request.META.get('HTTP_X_FORWARDED_PROTO', ''):
            request.is_secure = lambda:True
        try:
            real_ip = request.META['HTTP_X_FORWARDED_FOR']
            real_ip = real_ip.split(",")[-1].strip()
            request.META['REMOTE_ADDR'] = real_ip
        except KeyError:
            pass
        return None


class SSLRedirectMiddleware(object):
    """Redirect to SSL or non-SSL view.

    Whether a view is SSL secured is determined by:
        1. settings.SSL_ENABLED
        2. view_kwargs contain ``ssl``

    """
    def process_view(self, request, view_func, view_args, view_kwargs):
        is_view_secured = view_kwargs.pop('ssl', False) and settings.SSL_ENABLED
        if is_view_secured != request.is_secure():
            # Redirect this view
            request.is_secure = lambda:is_view_secured
            return HttpResponsePermanentRedirect(request.build_absolute_uri())
        return None

