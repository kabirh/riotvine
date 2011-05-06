import logging
from datetime import date, timedelta

from django.conf import settings
from django.db.models import Q

from rdutils import chunks
from fsq import FoursquareApi as FSQ
from registration.models import UserProfile
from twitter.models import TwitterProfile
from event.models import EventCheckin

_log = logging.getLogger('fsq.utils')

_USER, _PASS = settings.FOURSQUARE_USERNAME, settings.FOURSQUARE_PASSWORD
HEADERS = {
   'User-Agent': getattr(settings, 'FOURSQUARE_USER_AGENT', settings.USER_AGENT)
}


def approve_pending_friends(api=None):
    if not api:
        api = FSQ(HEADERS)
    p = api.get_pending_friends(_USER, _PASS)
    if not p or 'requests' not in p:
        return
    friends = p['requests']
    for f in friends:
        uid = f['id']
        resp = api.approve_friend(_USER, _PASS, uid)
    if friends:
        _log.warn("Approved %s 4sq friends:\n%s", len(friends), friends)
    return friends


def connect_uids(*args, **kwargs):    
    """Connect foursquare userids to our user profiles"""
    api = FSQ(HEADERS)
    approve_pending_friends(api)
    resp = api.get_friends(_USER, _PASS)
    _log.debug("4sq friends resp:\n%s", resp)
    if 'friends' not in resp:
        return
    friends = resp['friends']    
    n = 0
    connected = 0
    uid = []
    email = []
    twitter = []
    fb = []
    uid_map = {}
    for f in friends:
        uidx = unicode(f['id'])
        uid.append(uidx)
        emx = f.get('email', None)
        fbx = f.get('facebook', None)
        twx = f.get('twitter', None)
        if emx:
            emx = unicode(emx.lower())
            email.append(emx)
            uid_map[u'email-%s' % emx] = uidx
        if fbx:             
            fbx = unicode(fbx)
            fb.append(fbx)
            uid_map[u'fb-%s' % fbx] = uidx
        if twx:
            twx = twx.lower()
            twitter.append(twx)        
            uid_map[u'tw-%s' % twx] = uidx
    uids_done = {}        
    q = UserProfile.objects.active().filter(fsq_userid=u'') # only include profiles not yet connected to 4sq
    
    for email_chunk in chunks(email, 50):
        if not email_chunk:
            break
        qx = q.filter(user__email__in=email_chunk)
        for up in qx:
            key = u'email-%s' % up.user.email
            uid = uid_map.get(key, None)
            if uid and not uid in uids_done:
                up.fsq_userid = uid
                up.save()
                uids_done[uid] = up
            
    for fb_chunk in chunks(fb, 50):
        if not fb_chunk:
            break
        qx = q.filter(fb_userid__in=fb_chunk)
        for up in qx:
            key = u'fb-%s' % up.fb_userid
            uid = uid_map.get(key, None)
            if uid and not uid in uids_done:
                up.fsq_userid = uid
                up.save()
                uids_done[uid] = up
            
    q = TwitterProfile.objects.active().filter(user_profile__fsq_userid=u'')
    for tw_chunk in chunks(twitter, 50):
        if not tw_chunk:
            break
        qx = q.filter(screen_name_lower__in=tw_chunk)
        for t in qx:
            up = t.user_profile
            key = u'tw-%s' % t.screen_name_lower
            uid = uid_map.get(key, None)
            if uid and not uid in uids_done:
                up.fsq_userid = uid
                up.save()
                uids_done[uid] = up
                
    checkin_uids = uids_done.keys()
    # connect user_profiles to past checkins
    EventCheckin.objects.connect_profiles_to_checkins(checkin_uids, uids_done)
    if uids_done:
        _log.warn("Foursquare IDs connected (%s):\n%s", len(uids_done), uids_done)
