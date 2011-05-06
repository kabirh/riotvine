"""

Facebook API related utility functions

"""
import logging
import urllib2
import time
from facebook import Facebook
from hashlib import md5



_log = logging.getLogger('fb.utils')
_MAX_RETRIES = 1


def verify_sig(cookies, api_key, secret_key):
    """

    To generate the signature for these arguments, do the following:

        1. Remove the "fb_api_key_" prefix from all of the keys.
        2. Sort the array alphabetically by key.
        3. Concatenate all key/value pairs together in the format "k=v" 
           (omitting the signature itself, since that is what we are calculating).
        4. Append your secret key, which you can find by going to the Developers 
           application and following the link for your application.
        5. Take the md5 hash of the whole string.

    """
    sig = cookies.get(api_key, None)
    if not sig:
        return False
    prefix = u"%s_" % api_key
    plen = len(prefix)
    values = []
    for k,v in cookies.iteritems():
        if k.startswith(prefix):
            key = k[plen:]
            values.append((key, v))
    values.sort(key=lambda x:x[0])
    values = [u"%s=%s" % (k,v) for k,v in values]
    valuestr = u"".join(values) + secret_key
    computedsig = md5(valuestr).hexdigest()
    return computedsig == sig


def get_user_session(cookies, api_key):
    """Return a tuple with (API_KEY_user, API_KEY_session_key, API_KEY_ss)"""
    user = cookies.get(api_key + "_user", None)
    session = cookies.get(api_key + "_session_key", None)
    ss = cookies.get(api_key + "_ss", None)
    return (user, session, ss)


def get_mobile_session(auth_token, api_key, secret_key, retry=0):
    """Return a tuple with (API_KEY_user, API_KEY_session_key, API_KEY_ss)"""
    try:
        facebook = Facebook(api_key, secret_key, auth_token=auth_token)
        facebook.auth.getSession()
        user = facebook.uid and unicode(facebook.uid) or u''
        session = facebook.session_key
        ss = u''
        return (user, session, ss)
    except urllib2.URLError, ue:
        if retry < _MAX_RETRIES:
            # retry once
            time.sleep(.1)
            return get_mobile_session(auth_token, api_key, secret_key, retry=retry+1)
        else:
            _log.exception(ue)
            _log.warn("Could not get FB mobile session: %s", auth_token)
    except Exception, e:
        _log.exception(e)
        _log.warn("Could not get FB mobile session: %s", auth_token)
    return None, None, None


def get_user_info(api_key, secret_key, fb_session_key, fb_uid, retry=0):
    """Return a dictionary with the FB user's name and email address"""
    retval = {'name':None, 'email':None}
    try:
        facebook = Facebook(api_key, secret_key)
        facebook.session_key = fb_session_key
        info = facebook.users.getInfo([fb_uid], ['name', 'proxied_email'])[0]
        retval['name'] = info.get('name', None)
        retval['email'] = info.get('proxied_email', None)
    except urllib2.URLError, ue:
        if retry < _MAX_RETRIES:
            # retry once
            time.sleep(.1)
            return get_user_info(api_key, secret_key, fb_session_key, fb_uid, retry=retry+1)
        else:
            _log.exception(ue)
            _log.warn("Could not get FB user info: %s", fb_uid)
    except Exception, e:
        _log.exception(e)
        _log.warn("Could not get FB user info: %s", fb_uid)
    return retval


def get_connected_friends(api_key, secret_key, fb_session_key, fb_uid, retry=0):
    """Return a list with the FB user's friends' IDs that are connected to our app"""
    retval = []
    try:
        facebook = Facebook(api_key, secret_key)
        facebook.session_key = fb_session_key
        info = facebook.friends.getAppUsers()
        retval = info
    except urllib2.URLError, ue:
        if retry < _MAX_RETRIES:
            # retry once
            time.sleep(.1)
            return get_connected_friends(api_key, secret_key, fb_session_key, fb_uid, retry=retry+1)
        else:
            _log.exception(ue)
            _log.warn("Could not get FB friends: %s", fb_uid)
    except Exception, e:
        _log.exception(e)
        _log.warn("Could not get FB friends: %s", fb_uid)
    return retval


def delete_cookies(response, api_key, domain):
    """Delete FB cookies from the given response"""
    response.delete_cookie(api_key + '_user', domain=domain)
    response.delete_cookie(api_key + '_session_key', domain=domain)
    response.delete_cookie(api_key + '_expires', domain=domain)
    response.delete_cookie(api_key + '_ss', domain=domain)
    response.delete_cookie(api_key, domain=domain)
    response.delete_cookie('fbsetting_' + api_key, domain=domain)


def auto_friend(user_profile, new_friends):
    """Add new_friends to user specified by profile.
    
    `new_friends` is a set of user_profile ids
    
    """
    from registration.models import UserProfile, Friendship
    n = 0
    for profile in UserProfile.objects.active().filter(fb_userid__in=list(new_friends)):
        # establish bi-directional friendship immediately
        Friendship.objects.make_friends(user_profile, profile, source='fb')
        n += 1
    return n
