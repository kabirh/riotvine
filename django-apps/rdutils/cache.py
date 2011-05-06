"""

Typical import:

from rdutils.cache import key_suffix, short_key, clear_keys, cache

"""

import logging
import uuid

from django.utils.hashcompat import sha_constructor
from django.utils.encoding import force_unicode
from django.conf import settings
from django.core import cache


_log = logging.getLogger('rdutils.cache')


_CACHE_NAMESPACE = getattr(settings, 'CACHE_NAMESPACE', 'x')
_CACHE_RECORD_PREFIXES = getattr(settings, 'CACHE_RECORD_PREFIXES', ())


def shorten_key(key):
    try:
        return sha_constructor(key).hexdigest()
    except UnicodeEncodeError:
        return sha_constructor(key.encode('utf-8', 'replace')).hexdigest()

short_key = shorten_key # alias


def _make_key(key_type, rec_id):
    """DRY method to generate record keys."""
    return u'%s:rec_key:%s-%s' % (_CACHE_NAMESPACE, key_type, rec_id)


def get_cache_key_type(cache_key):
    for pfx in _CACHE_RECORD_PREFIXES:
        if cache_key.startswith(pfx):
            # example: if cache key is xf-usr-xyz, return `usr`
            return pfx.split('-')[1]
    return cache_key


def get_cache_key_suffix(cache_key, rec_id, expire_time=720000):
    """Return key's value from cache or return newly generated value"""
    key_type = get_cache_key_type(cache_key)
    if key_type:
        rec_key = _make_key(key_type, rec_id)
        value = cache.cache.get(rec_key, None)
        if value is None:
            value = unicode(uuid.uuid4())
            if expire_time:
                cache.cache.set(rec_key, value, expire_time)
            else:
                cache.cache.set(rec_key, value)
        return value
    return u''

key_suffix = get_cache_key_suffix # shorter alias

def invalidate_cached_key_suffix(key_type, rec_id):
    """Delete key from cache"""
    try:
        rec_key = _make_key(key_type, rec_id)
        cache.cache.delete(rec_key)
    except AttributeError: # This only happens when using the Debug Toolbar
        pass

# shorter aliases:
clear_cached_keys = invalidate_cached_key_suffix
clear_keys = invalidate_cached_key_suffix

