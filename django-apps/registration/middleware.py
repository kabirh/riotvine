"""

Middleware classes to grab a site visitor's zip code.

"""
import logging
import random
import string
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth.models import User

from rdutils.email import email_template
from registration.models import UserProfile


_log = logging.getLogger('registration.middleware')
_CHAR_LIST = list(string.ascii_letters + string.digits)
# Don't use zero, one, and the letters O, I, L as they can be 
# confused for other letters or numbers.
_CHAR_LIST.remove('0')
_CHAR_LIST.remove('1')
_CHAR_LIST.remove('O')
_CHAR_LIST.remove('I') 
_CHAR_LIST.remove('L')
_CHAR_LIST.remove('o')
_CHAR_LIST.remove('i') 
_CHAR_LIST.remove('l')


class SignUpMiddleware(object):
    """Add email address and opt-in preference from session to signed up user's account.

    If user doesn't have a password, generate a new one and send a welcome email.

    """
    def process_request(self, request):
        if request.user.is_authenticated():
            if 'email' not in request.session:
                return None
            s = request.session
            do_email, password, is_temp_password = False, None, False
            email = s.pop("email", None)
            has_opted_in = s.pop('has_opted_in', None)
            password = s.pop('password', None)
            u, p = request.user, request.user_profile
            user_dirty, profile_dirty = False, False
            if email:
                u.email = email
                p.send_reminders = True
                p.send_favorites = True
                p.is_verified = settings.ACCOUNT_EMAIL_VERIFICATION_DEFAULT
                u.date_joined = datetime.now()
                p.is_sso = False
                do_email = True
                user_dirty = True
                profile_dirty = True
            if has_opted_in is not None:
                p.has_opted_in = has_opted_in
                profile_dirty = True
            # If the user account was created in the last 2 hours,
            # and there's no password, set a new password and
            # send a welcome message to this user.
            if email and not u.password:
                threshold = datetime.now() - timedelta(hours=2)
                if u.date_joined > threshold:
                    if not password:
                        is_temp_password = True
                        password = ''.join(random.sample(_CHAR_LIST, 6))
                    u.set_password(password)
                    user_dirty = True
                    do_email = True
            if user_dirty:
                u.save()
            if profile_dirty:
                p.save()
            if user_dirty:
                p = u.get_profile()
                request.user_profile = p
            if do_email:
                ctx = {'user':u, 'user_profile':p}
                if is_temp_password:
                    ctx['temp_password'] = password
                else:
                    ctx['password'] = password
                email_template('Welcome to %s!' % settings.UI_SETTINGS['UI_SITE_TITLE'],
                               'registration/email/welcome.html', ctx, to_list=[u.email])
        return None

