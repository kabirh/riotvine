import logging
import os
import os.path
import logging, logging.config
import urllib2
from datetime import date, datetime, timedelta

from django.conf import settings
from django.utils import simplejson as json
from django.utils.http import urlencode

_PARAMS = {
    'url':getattr(settings, 'LASTFM_API_URL', 'http://ws.audioscrobbler.com/2.0/'),
    'api_key':settings.LASTFM_API_KEY,
}
_URL = u"%(url)s?method=artist.getinfo&format=json&api_key=%(api_key)s&%%s" % _PARAMS

_log = logging.getLogger('lastfm.__init__')
_x = _log

def _get_artist(artist):
    artist_dictionary = {}
    px = {'artist':artist}
    px = urlencode(px)
    url = _URL % px
    req = urllib2.Request(url)
    req.add_header("Content-type", "application/x-www-form-urlencoded")
    req.add_header('User-Agent', settings.USER_AGENT)
    try:
        resp = urllib2.urlopen(req)
    except Exception, e:
        # retry once
        time.sleep(20)
        resp = urllib2.urlopen(req)
    ret = resp.read()
    resp.close()
    results = json.loads(ret)
    try:
        if results:
            artist_dictionary = results.get('artist', {})
            artist_dictionary['img'] = u''
            if 'image' in artist_dictionary:
                for x in artist_dictionary['image']:
                    if x['size'] == "extralarge":
                        image = x['#text']
                        artist_dictionary['img'] = image
        else:
            artist_dictionary = {}
    except Exception, e:
        _x.warn("Result JSON could not be processed:\n(%s)\nURL:\n%s", ret, url)
        _x.exception(e)
        artist_dictionary = {}
    return artist_dictionary


def get_artist(artist):
    try:
        return _get_artist(artist)
    except Exception, e:
        _x.warn("Could not reach last.fm to get artist info")
        _x.exception(e)
        return {}

