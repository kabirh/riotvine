import logging

from django.conf import settings
from django.http import HttpResponseRedirect


_log = logging.getLogger('artist.middleware')


class ArtistRedirectorMiddleware(object):
    """Redirect to the page that the logged in artist was trying to reach before
    he was detoured into filling out his artist profile.

    Works in collusion with: ``artist.decorators.artist_account_required``

    """
    def process_request(self, request):
        if request.user.is_authenticated() and request.user.get_profile().is_artist_profile_complete:
            next = request.session.pop(settings.ARTIST_REDIRECT_FIELDNAME, False)
            if next:
                _log.debug('Redirecting to %s', next)
                return HttpResponseRedirect(next)
        return None

