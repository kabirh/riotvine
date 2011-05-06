import logging
import urllib2
import time
import os
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import simplejson as json
from django.core.cache import cache
from django.utils.http import urlencode

from rdutils.cache import shorten_key
from twitter import TwitterAPI
from twitter.models import BlackList, TwitterProfile


PROTOCOL = (settings.DEV_MODE and os.name == 'nt') and 'http' or 'https'

_log = logging.getLogger('twitter.utils')
TWITTER_PROFILE_URL = getattr(settings, 'TWITTER_PROFILE_URL', 'http://twitter.com/users/show.json?%s')
TWITTER_SEARCH_URL = getattr(settings, 'TWITTER_SEARCH_URL', 'http://search.twitter.com/search.json?%s')
TWITTER_FOLLOWEES_URL = getattr(settings, 'TWITTER_FOLLOWEES_URL', 'http://twitter.com/friends/ids.json?%s') # user_id=X&cursor=-1
TWITTER_FOLLOWERS_URL = getattr(settings, 'TWITTER_FOLLOWERS_URL', 'http://twitter.com/followers/ids.json?%s') # user_id=X&cursor=-1
# TWITTER_FOLLOWERS_PER_PAGE = getattr(settings, 'TWITTER_FOLLOWERS_PER_PAGE', 5000)
# TWITTER_FOLLOWERS_MAX_PAGES = getattr(settings, 'TWITTER_FOLLOWERS_MAX_PAGES', 1)
TWITTER_TIME_FORMAT_SEARCH = '%a, %d %b %Y %H:%M:%S +0000'
TWITTER_TIME_FORMAT_STATUS = '%a %b %d %H:%M:%S +0000 %Y'
TWITTER_TIME_FORMATS = (TWITTER_TIME_FORMAT_SEARCH, TWITTER_TIME_FORMAT_STATUS)

def post_to_twitter(user, status):
    """Helper function to post a user's status to her authorized Twitter account."""
    posting_status = ''
    try:
        tw_prof = user.get_profile().twitter_profile
        if tw_prof and tw_prof.access_token:
            _log.debug("Posting %s's status - %s", user.username.title(), status)
            tw = TwitterAPI()
            posting_status = tw.post_status(tw_prof.access_token, status)
            tw.close()
            s = json.loads(posting_status)
            if s.get('id', False):
                _log.debug("Posted %s's status - %s", user.username.title(), s.get("text", "NO TEXT"))
                return s
            else:
                _log.error("Could not post %s's status:\n%s\n", user.username.title(), posting_status)
        return False
    except Exception, e:
        _log.exception(e)
        if posting_status:
            _log.debug("Posting status error:\n%s", posting_status)
            if tw_prof and 'invalid oauth request' in posting_status.lower() or 'failed to validate oauth' in posting_status.lower():
                # Remove unusable access token
                tw_prof.access_token = u''
                tw_prof.save()
        return False


def convert_timestamp(twitter_timestring, fill_dict=None, fill_key='created_at'):
    """Return Python datetime for the given twitter timestring.

    If fill dictionary is provided, populate its fill_key with TZ adjusted timestamp.

    """
    # Mon, 15 Jun 2009 19:14:05 +0000 == "%a, %d %b %Y %H:%M:%S +0000" 
    # Tue Apr 07 22:52:51 +0000 2009 == "%a %b %d %H:%M:%S +0000 %Y" 
    for tf in TWITTER_TIME_FORMATS:
        try:
            t = time.strptime(twitter_timestring, tf)
            dt = datetime(*t[:6]) - timedelta(hours=settings.UTC_TIME_DIFFERENCE) # Eastern time adjustment
            if fill_dict:
                fill_dict[fill_key] = dt.strftime(tf)
            return dt
        except Exception, e:
            pass
    return datetime.now()


class NotInBlackList(object):
    """Blacklist and dupe checker filter function"""
    def __init__(self):
        self.blacklist = BlackList.objects.blacklist_set()
        self.count = 0
        self.text_map = {} # dictionary of tweet text; used for dupe checking

    def __call__(self, tweetdict):
        """List filter function. Return True to include element. False to reject it."""
        if self.count == 10000:
            self.count = 0
            self.blacklist = BlackList.objects.blacklist_set() # refresh BL
        self.count += 1
        screenname = tweetdict['from_user'].lower()
        if screenname in self.blacklist:
            return False
        txt = tweetdict.get('text', u'')
        if not txt:
            return False # disallow empty tweets
        if self.text_map.get(txt, False):
            return False # disallow dupe text
        self.text_map[txt] = True
        return True


def search(params, rpp=100, lang='all', count=0):
    params_q, urlx, object_id, object_type = None, None, None, None
    try:
        object_type = params.pop('object_type', 'no_type')
        object_id = params.pop('object_id', 'no_id')
        # api_count
        api_count = cache.get('twitter_search_count', 0)
        api_count = api_count % 1000000 # reset after every million searches
        cache.set('twitter_search_count', api_count+1, 300000)
        if not 'lang' in params:
            params['lang'] = lang
        if not 'rpp' in params:
            params['rpp'] = rpp
        if not params.get('q', False):
            # nothing to search
            return []       
        k = params.items()
        k.sort()
        params_q = urlencode(params)
        cache_key = shorten_key(u'%s' % k)
        tweets = cache.get(cache_key, None)
        if tweets is None:
            _log.debug("Searching Twitter: %s", params_q)
            urlx = TWITTER_SEARCH_URL % params_q
            req = urllib2.Request(urlx)
            req.add_header("Content-type", "application/x-www-form-urlencoded")
            req.add_header('User-Agent', settings.USER_AGENT)
            req.add_header('Referer', 'http://riotvine.com/')
            resp = urllib2.urlopen(req)
            ret = resp.read()
            resp.close()
            results = json.loads(ret)
            # Remove blacklisted users
            tweets = filter(NotInBlackList(), results.get('results', []))
            cache.set(cache_key, tweets, 180)
            if api_count % 25 == 0:
                # back off for a few seconds after every 25 searches
                zzz = 5
                if api_count % 100 == 0:
                    zzz += 10
                if api_count % 400 == 0:
                    zzz += 10
            else:
                zzz = settings.TWITTER_SEARCH_SLEEP
            time.sleep(zzz) # search throttle
        return tweets
    except urllib2.HTTPError, h: 
        # e.g.: raise HTTPError(req.get_full_url(), code, msg, hdrs, fp)
        msg = h.info() # httplib.HttpMessage
        try:
            retry_after = int(msg.get('Retry-After', 0))
        except:
            retry_after = 0
        if h.code != 403: # Skip bad search warning here; it's logged later down below
            if h.code not in (502, 503, 404, 420):
                _log.exception(h)
                _log.warn("Search count: %s\n%s\n\n%s\n\nRetry count: %s\n\n%s\n%s - %s", api_count, params, unicode(msg), count,  urlx, object_type, object_id)
        if h.code in (503, 502, 420): # grab retry-after header (we are being rate-limited)
            # 503 or 420 - we are being rate limited
            # 502 - bad gateway - Twitter overloaded
            if h.code in (503, 420): # reset twitter search count on rate limitation
                cache.set('twitter_search_count', 0, 300000) # reset count at throttle
            if not retry_after:
                retry_after = 10
            throttle = retry_after * 1.1
            time.sleep(throttle)
            retry_after = 0
            _log.debug("%s \n\nThrottled by %s seconds [status: %s]\n%s - %s", params, throttle, h.code, object_type, object_id)
            if count < settings.TWITTER_SEARCH_RETRY_TIMES:
                p = dict(object_type=object_type, object_id=object_id)
                p.update(params)
                return search(p, rpp=rpp, lang=lang, count=count+1) # retry
        elif h.code == 403:
            _log.warn("Bad search\n%s\n%s\n%s - %s", params, urlx, object_type, object_id)
            retry_after = 5
        elif h.code == 404:
            pass # skip and move on
        else:
            retry_after = 10
        if retry_after:
            throttle = retry_after * 1.1
            time.sleep(throttle)
            retry_after = 0
        return []
    except Exception, e:
        _log.exception(e)
        return []


def quote_hashtags(hashtags):
    x = []
    for w in hashtags:
        if len(w.replace("'",'').replace('"','').replace(' ','').replace('&', '').strip()) < 2:
            # discard single letter searches
            continue
        for s in settings.TWITTER_BAD_HASHTAGS:
            if s in w:
                w = None
                break
        if not w:
            continue
        w = w.strip()
        if ' ' in w and not '"' in w:
            w = u'"%s"' % w
        x.append(w)
    return x


def hashtags_to_q(hashtags, quote=True, operator=" OR "):
    if quote:
        hashtags = quote_hashtags(hashtags)
    return operator.join(hashtags)


def hashtags_to_q_list(hashtags, quote=True, operator=" OR ", maxlength=140):
    """Return list of search queries such that no query is longer than 140 characters"""
    qlist = []
    overflow = []
    h = hashtags[:]
    while True:
        q = hashtags_to_q(h)
        if len(q) > maxlength:
            overflow.append(h.pop())
        else:
            if q:
                qlist.append(q)
            break
    if overflow:
        qlist.extend(hashtags_to_q_list(overflow, quote=quote, operator=operator, maxlength=maxlength))
    return qlist


def get_tweets_by_hashtag(hashtags, limit=25):
    """Return list of tweets by hashtag.

    `hashtags` is a list.

    """
    q = hashtags_to_q(hashtags)
    tweets = search({'q':q}, rpp=limit)
    return tweets


def get_followers_or_followees(twitter_user_id, twitter_url, retry=0, oauth=False, access_token=''):
    """Return a list of followers or followees of a Twitter user"""
    x = []
    tw = None
    params = {'user_id':twitter_user_id, 'cursor':'-1'}
    try:
        px = urlencode(params)
        if oauth:
            if not access_token:
                tw_prof = TwitterProfile.objects.active().filter(
                    appuser_id=twitter_user_id
                ).exclude(access_token=u'').order_by("-updated_on")[:1].get()
                access_token = tw_prof.access_token
            tw = TwitterAPI()
            if PROTOCOL == 'https':
                twitter_url = twitter_url.replace('http:', 'https:')
            _url = twitter_url % px
            _log.debug("OAuth URL %s" % _url)
            ret = tw.get_url(access_token, _url)
            tw.close()
        else:
            _url = twitter_url % px
            _log.debug(_url)
            req = urllib2.Request(_url)
            req.add_header("Content-type", "application/x-www-form-urlencoded")
            req.add_header('User-Agent', settings.USER_AGENT)
            resp = urllib2.urlopen(req)
            ret = resp.read()
            resp.close()
        results = json.loads(ret)
        if type(results) == dict:
            x = results.get('ids', [])
        else:
            x = results
        time.sleep(settings.TWITTER_SLEEP)
        return x
    except urllib2.HTTPError, h:
        if h.code == 401 and retry < 2:
            # Try with OAuth
            return get_followers_or_followees(twitter_user_id, twitter_url, retry=retry+1, oauth=True, access_token=access_token)
        _log.error("%s failed for twitter id: %s (HTTP Error)", twitter_url, twitter_user_id)
        _log.exception(h)
        if h.code in (503, 502, 420):
            time.sleep(30 + retry*30) # throttle
        if x or retry > 1:
            return x
        return get_followers_or_followees(twitter_user_id, twitter_url, retry=retry+1, oauth=oauth, access_token=access_token)
    except Exception, e:
        _log.error("%s failed for twitter id: %s (non-HTTP error)", twitter_url, twitter_user_id)
        _log.exception(e)
        time.sleep(settings.TWITTER_SLEEP)
        return x
    finally:
        if tw:
            tw.close()


def get_followees(twitter_user_id, access_token=''):
    return get_followers_or_followees(twitter_user_id, TWITTER_FOLLOWEES_URL, access_token=access_token)


def get_followers(twitter_user_id, access_token=''):
    return get_followers_or_followees(twitter_user_id, TWITTER_FOLLOWERS_URL, access_token=access_token)


def get_friends(twitter_user_id, followees, followers):
    """Return a list of this user's friends (return a set of twitter user_ids).

    Users A and B are considered friends if and only if A and B follow each other.

    """
    if not followees:
        return set()
    if not followers:
        return set()
    if not isinstance(followees, set):
        followees = set(followees)
    if not isinstance(followers, set):
        followers = set(followers)
    return followees & followers


def get_background_url(twitter_user_id):
    params = {'user_id':twitter_user_id,}
    _url = None
    try:
        _url = TWITTER_PROFILE_URL % urlencode(params)
        _log.debug(_url)
        req = urllib2.Request(_url)
        req.add_header("Content-type", "application/x-www-form-urlencoded")
        req.add_header('User-Agent', settings.USER_AGENT)
        resp = urllib2.urlopen(req)
        ret = resp.read()
        resp.close()
        results = json.loads(ret)
        bg_url = results.get('profile_background_image_url', None)
        bg_tile = results.get('profile_background_tile', False)
        return bg_url, bg_tile
    except Exception, e:
        _log.exception(e)
        _log.warn("Failed to retrieve URL %s", _url)
        return None, True

