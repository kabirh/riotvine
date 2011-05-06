import logging

from django.conf import settings

from fb.utils import delete_cookies
from fb.views import get_fb_session

_log = logging.getLogger('fb.middleware')


class FBMiddleWare(object):
    def process_request(self, request):
        if request.user.is_authenticated():
            fb_uid, fb_session_key, fb_session_secret = get_fb_session(request)
            user_profile = getattr(request, 'user_profile', None)
            if user_profile:
                if fb_session_key and not user_profile.fb_session_key and user_profile.fb_userid:
                    # store constant auth session key
                    if fb_session_key.endswith(user_profile.fb_userid):
                        user_profile.fb_session_key = fb_session_key
                        user_profile.save()
                if 'fb_uid' in request.session:
                    return
                if fb_uid and user_profile.fb_userid == fb_uid:
                    request.session['fb_uid'] = fb_uid
                elif not fb_uid and user_profile.fb_userid:
                    request.session['fb_uid'] = user_profile.fb_userid

    def process_response(self, request, response):
        # Delete FB Connect cookies
        # FB Connect JavaScript may add them back, but this will ensure they're deleted if they should be
        if getattr(request, "delete_fb_cookies", False):
            delete_cookies(response, settings.FB_API_KEY, domain=settings.SESSION_COOKIE_DOMAIN)
        return response

