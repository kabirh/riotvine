'''

Callbacks for non-desktop apps are now supported with these rules: 
- When making the call to request_token [4] (server-to-server), you can pass 
&oauth_callback=[url here] 
- The response from request_token will contain oauth_callback_confirmed=true 
to confirm we received it. 
- The user will be sent to twitter.com as usual 
- When the user is finished they will be redirected to the URL provided in 
the first step along with a new parameter, oauth_verifier [1] 
- The call to access_token [5] to exchange the request token for an access 
token MUST contain the oauth_verifier parameter as sent in the redirect. 
- If you want to use your pre-configured callback, then do not include a 
oauth_callback parameter. 

'''
import logging
import oauth

from django.conf import settings
from django.http import HttpResponseRedirect, Http404, HttpResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.core.urlresolvers import reverse
from django.utils import simplejson
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _
from django.shortcuts import get_object_or_404

from common.utils import add_message
from rdutils.social import save_open_profile
from rdutils.render import render_view, paginate
from twitter import TwitterAPI
from twitter.utils import post_to_twitter


_log = logging.getLogger('twitter.views')
TWITTER_GENERAL_STATUS_FORMAT = getattr(settings, 'TWITTER_GENERAL_STATUS_FORMAT', '%(status)s')


def authorize(request):
    """Get an unauth token and redirect user to Twitter's authorization URL."""
    next = request.GET.get('next', None)
    if next:
        request.session['TWITTER_NEXT_URL'] = next
    try:
        tw = TwitterAPI()
        try:
            token = tw.get_unauthorised_request_token()
        except KeyError:
            # retry once
            tw.close()
            tw = TwitterAPI()
            token = tw.get_unauthorised_request_token()
        request.session['TWITTER_UNAUTH_TOKEN'] = token.to_string()
        auth_url = tw.get_authorisation_url(token)
        response = HttpResponseRedirect(auth_url)
        tw.close()
        return response
    except Exception, e:
        _log.exception(e)
        if request.user.is_authenticated():
            add_message(request, u"We are unable to connect to Twitter at the moment. Please try again in a few minutes.")
        else:
            add_message(request, u"We are unable to connect to Twitter at the moment. Please continue signing up below. You will be able to connect your account to Twitter later from our homepage.")
        return _denied_response(request)


def _denied_response(request):
    if request.user.is_authenticated():
        next = request.session.pop('TWITTER_NEXT_URL', reverse('home'))
        return HttpResponseRedirect(next + "?open_auth_denied=y")
    else:
        return HttpResponseRedirect(reverse('register') + "?open_auth_denied=y")


def callback(request):
    """This is where Twitter will redirect the user after this app has been authorized."""
    try:
        unauthed_token = request.session.get('TWITTER_UNAUTH_TOKEN', None)
        oauth_verifier = request.GET.get('oauth_verifier', None)
        try:
            if unauthed_token:
                del request.session['TWITTER_UNAUTH_TOKEN']
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
        tw = TwitterAPI()
        try:
            access_token = tw.exchange_request_token_for_access_token(token, oauth_verifier)
        except KeyError:
            tw.close()
            return _denied_response(request)
        twitter_profile = tw.get_profile(access_token)
        tw.close()
        if twitter_profile:
            _log.debug("Twitter profile downloaded:\n%s", twitter_profile)
            try:
                p = simplejson.loads(twitter_profile)
            except Exception, e:
                # try one more time
                try:
                    tw = TwitterAPI()
                    twitter_profile = tw.get_profile(access_token)
                    tw.close()
                    _log.debug("Twitter profile downloaded on retry:\n%s", twitter_profile)
                    if not twitter_profile:
                        raise Exception("OAuth error: retry failed on get_profile")
                    p = simplejson.loads(twitter_profile)
                except Exception, e:
                    _log.warn("Twitter profile could not be JSON decoded.\n%s", twitter_profile)
                    _log.exception(e)
                    add_message(request, u"We are unable to connect to Twitter at the moment. Please try again in a few minutes.")
                    return _denied_response(request)
            _log.debug(p)
            screen_name = p.get('screen_name')
            full_name = p.get('name', p['screen_name'])
            # Split full_name into first name and last name
            x = full_name.split(' ', 1)
            first_name, last_name = u'', u''
            if len(x) > 1:
                first_name, last_name = x[0], x[1]
            elif len(x) == 1:
                first_name, last_name = u'', x[0]
            profile_image = p.get('profile_image_url', '')
            if '/images/default_profile' in profile_image:
                profile_image = ''
            profile = dict(
                profile_type=u'twitter',
                screen_name=screen_name,
                first_name=first_name,
                last_name=last_name,
                appuser_id=p['id'],
                profile_image_url=profile_image,
                access_token=access_token.to_string()
            )
            if request.user.is_authenticated():
                user = request.user
                p = save_open_profile(user, profile)
                add_message(request, u"You've connected your Twitter account successfully.")
                # user.message_set.create(message=_(u"Thank you for authorizing us to update your Twitter status!"))
            else:
                request.session['OPEN_PROFILE'] = profile
        if request.user.is_authenticated():
            next = request.session.pop('TWITTER_NEXT_URL', reverse('home'))
            return HttpResponseRedirect(next + '?open_profile=twitter')
        else:
            next = request.session.pop('TWITTER_NEXT_URL', reverse('register'))
            return HttpResponseRedirect(next + '?open_profile=twitter')
    except Exception, e:
        _log.exception(e)
        add_message(request, u"We are unable to connect to Twitter at the moment. Please try again in a few minutes.")
        return _denied_response(request)


@login_required
def post_status(request):
    mesg = None
    ret_ctx = {} # The return context sent to AJAX callers
    ret_ctx['success'] = False
    if request.method == 'POST':
        status = request.POST.get('status_text', '').strip()
        if not status:
            status = request.POST.get('status', '').strip()
        mesg = u"Status could not be posted to Twitter."
        if status:
            status = TWITTER_GENERAL_STATUS_FORMAT % {'status':status}
            posted = post_to_twitter(request.user, status)
            if posted:
                mesg = u"Status posted to Twitter!"
                ret_ctx['success'] = True
    if request.is_ajax():
        ret_ctx['message'] = mesg
        return HttpResponse(simplejson.dumps(ret_ctx), mimetype='application/json')
    if mesg:
        request.user.message_set.create(message=mesg)
    next = request.REQUEST.get('next', '')
    if not next:
        next = reverse('home')
    return HttpResponseRedirect(next)

