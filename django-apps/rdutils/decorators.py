"""
General purpose decorators
"""
from django.core.cache import cache
from django.utils.datastructures import SortedDict

from rdutils.text import slugify


def construct_cache_key(cache_key_prefix, *args, **kwargs):
    sdict = SortedDict(kwargs)
    return slugify("%s-%s-%s" % (cache_key_prefix, args, sdict))


def function_cache(cache_key_prefix):
    """A decorator that caches a function's return value."""
    def _dec(fn):
        def _wrapper(*args, **kwargs):
            cache_key = construct_cache_key(cache_key_prefix, *args, **kwargs)
            ret_val = cache.get(cache_key, None)
            if ret_val is None:
                ret_val = fn(*args, **kwargs)
                cache.set(cache_key, ret_val)
            return ret_val
        return _wrapper
    return _dec


def attribute_cache(cache_keyname):
    """A decorator that caches a class method's return value per instance."""
    cache_keyname = cache_keyname + '_cache'
    def _dec(fn):
        def _wrapper(self, *args, **kwargs):
            if hasattr(self, cache_keyname):
                return getattr(self, cache_keyname)
            else:
                ret_val = fn(self, *args, **kwargs)
                setattr(self, cache_keyname, ret_val)
                return ret_val
        return _wrapper
    return _dec

