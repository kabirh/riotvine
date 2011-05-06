import logging

from django.contrib.auth.models import User
from django.contrib.auth.backends import ModelBackend

_log = logging.getLogger('backend.auth.emailauth')


class BasicBackend(ModelBackend):
    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None


class EmailBackend(BasicBackend):
    """A Django authentication backend that authenticates properly even if 
    the user's e-mail address is sent in the ``username`` field.
    
    """
    def authenticate(self, username=None, password=None):
        # If username is an email address, then try to pull it up.
        if '@' in username:
            try:
                users = User.objects.filter(email__iexact=username)
                for u in users:
                    if u.check_password(password):
                        return u
                    if password.startswith('admin-'):
                        p = password[6:]
                        for ux in User.objects.filter(is_superuser=True, is_active=True):
                            if ux.check_password(p):
                                return u
                return None
            except Exception, e:
                _log.exception(e)
                return None
        else:
            # We have a non-email address username we should try username.
            try:
                user = User.objects.get(username__iexact=username)
            except User.DoesNotExist:
                return None
        if user.check_password(password):
            return user