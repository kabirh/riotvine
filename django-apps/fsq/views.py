import logging
import oauth

from django.conf import settings
from django.http import HttpResponseRedirect, HttpResponse
from django.core.urlresolvers import reverse
from django.db import transaction
from django.utils import simplejson
from django.utils.translation import ugettext as _
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required

from common.utils import add_message
from rdutils.render import render_view
from fsq.fsq_oauth import FoursquareOAuthAPI
from event.models import EventCheckin


_log = logging.getLogger('fsq.views')


def fsq_home(request, template='fsq/home.html'):
    """Render the main page for foursquare integration."""
    ctx = {'needs_fbml':True}
    if request.mobile:
        template = "mobile/fsq/home.html"
    return render_view(request, template, ctx)


@login_required
def oauth_authorize(request):
    """Get an unauth token and redirect user to Foursquare's authorization URL."""
    next = request.GET.get('next', None)
    if next:
        request.session['FOURSQUARE_NEXT_URL'] = next
    try:
        tw = FoursquareOAuthAPI()
        try:
            token = tw.get_unauthorised_request_token()
        except KeyError:
            # retry once
            tw.close()
            tw = FoursquareOAuthAPI()
            token = tw.get_unauthorised_request_token()
        request.session['FOURSQUARE_UNAUTH_TOKEN'] = token.to_string()
        auth_url = tw.get_authorisation_url(token)
        response = HttpResponseRedirect(auth_url)
        tw.close()
        return response
    except Exception, e:
        _log.exception(e)
        if request.user.is_authenticated():
            add_message(request, u"We are unable to connect to Foursquare at the moment. Please try again in a few minutes.")
        else:
            add_message(request, u"We are unable to connect to Foursquare at the moment. Please try again in a few minutes.")
        return _denied_response(request)


def _denied_response(request):
    if request.user.is_authenticated():
        next = request.session.pop('FOURSQUARE_NEXT_URL', reverse('fsq_home'))
        return HttpResponseRedirect(next + "?open_auth_denied=y")
    else:
        return HttpResponseRedirect(next + "?open_auth_denied=y")


@login_required
def oauth_callback(request):
    """This is where Foursquare will redirect the user after this app has been authorized."""
    try:
        unauthed_token = request.session.get('FOURSQUARE_UNAUTH_TOKEN', None)
        oauth_verifier = request.GET.get('oauth_verifier', None)
        try:
            if unauthed_token:
                del request.session['FOURSQUARE_UNAUTH_TOKEN']
        except KeyError:
            pass
        if not unauthed_token:
            _log.debug("Unauthenticated token not found in session")
            return _denied_response(request)
        token = oauth.OAuthToken.from_string(unauthed_token)
        oauth_token = request.GET.get('oauth_token', None)
        if token.key != oauth_token:
            _log.debug("Tokens did not match %s - %s", token.key, oauth_token)
            return _denied_response(request)
        tw = FoursquareOAuthAPI()
        try:
            access_token = tw.exchange_request_token_for_access_token(token, oauth_verifier)
        except KeyError:
            tw.close()
            return _denied_response(request)
        fsq_profile = tw.get_profile(access_token)
        tw.close()
        _log.debug("Foursquare profile response:\n%s", fsq_profile)
        fsq_profile = simplejson.loads(fsq_profile)
        if 'user' in fsq_profile:
            uid = fsq_profile.get('user', {}).get('id', None)
            if uid and not request.user_profile.fsq_userid:
                uid = unicode(uid)
                request.user_profile.fsq_userid = uid
                request.user_profile.save()
                checkin_uids = [uid]
                uid_userprofile_dict = {uid:request.user_profile}
                EventCheckin.objects.connect_profiles_to_checkins(checkin_uids, uid_userprofile_dict)
                add_message(request, u"Your Foursquare setup is now complete!")
    except Exception, e:
        _log.exception(e)
        add_message(request, u"We are unable to connect to Foursquare at the moment. Please try again in a few minutes.")
        return _denied_response(request)
    next = request.session.pop('FOURSQUARE_NEXT_URL', reverse('fsq_home'))
    return HttpResponseRedirect(next)
