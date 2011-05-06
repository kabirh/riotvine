import logging

from django.conf import settings
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _


_log = logging.getLogger('artist.decorators')


def artist_account_required(view_func, url_name='login'):
    """Ensure that a view function is called only if the current user is an artist.

    This is implemented as a decorator that redirects the user to artist registration 
    if necessary.

    The session parameter ``settings.ARTIST_REDIRECT_FIELDNAME`` records where the
    user was trying to go before he was redirected. This value may be 
    used by ``artist.middleware.ArtistRedirectorMiddleware``.
    
    ``url_name`` is the URL to redirect a non-authenticated user to.
        For example: login (default) or register_artist

    """
    def decorated_view(request, *args, **kwargs):
        if request.user.is_authenticated():
            if request.user_profile.is_artist_profile_complete:
                try:
                    del request.session[settings.ARTIST_REDIRECT_FIELDNAME]
                except KeyError:
                    pass
                return view_func(request, *args, **kwargs)
            else:
                if request.user_profile.is_artist:
                    # Allow artist an opportunity to complete missing profile elements
                    try:
                        artist = request.user_profile.artist
                        if artist and not artist.has_payment_info:
                            request.user.message_set.create(message=_('Please complete your PayPal or Google Checkout account information below to proceed.'))
                    except:
                        request.user.message_set.create(message=_('Please complete your profile information below to proceed.'))
                    url = reverse('update_artist_profile')
                    if not request.session.get(settings.ARTIST_REDIRECT_FIELDNAME, False):
                        request.session[settings.ARTIST_REDIRECT_FIELDNAME] = request.path
                    _log.debug('Redirecting user %s to %s', request.user.username, url)
                else:
                    # Redirect non-artist (fan) to homepage
                    url = reverse('home')
                return HttpResponseRedirect(url)
        else:
            if not request.session.get(settings.ARTIST_REDIRECT_FIELDNAME, False):
                request.session[settings.ARTIST_REDIRECT_FIELDNAME] = request.path
            url = reverse(url_name)
            _log.debug('Redirecting anonymous user to %s?next=%s', url, request.path)
            return HttpResponseRedirect('%s?next=%s'% (url, request.path))
    return decorated_view

