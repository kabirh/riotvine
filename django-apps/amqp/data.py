"""

API to access AMQP correlation data.

Data is stored either in CouchDB or in Django cache.

"""

try:
    import couchdb
except ImportError:
    pass

try:
    import cjson as json
except ImportError:
    from django.utils import simplejson as json

from django.core import cache
from django.conf import settings


class BaseDataStorage(object):
    def close(self):
        pass

    def __getitem__(self, key):
        raise NotImplementedError("Implement this!")

    def __setitem__(self, key, doc):
        raise NotImplementedError("Implement this!")

    def __delitem__(self, key):
        raise NotImplementedError("Implement this!")


class CachedDataStorage(BaseDataStorage):
    def __init__(self):
        cache.cache.close() # always start with a fresh connection

    def close(self):
        if hasattr(cache.cache, 'close'):
            cache.cache.close()

    def __getitem__(self, key):
        return cache.cache.get(key)

    def __setitem__(self, key, doc):
        cache.cache.set(key, doc, 1800*16) # cache for 8 hours

    def __delitem__(self, key):
        cache.cache.delete(key)


class CouchDbDataStorage(BaseDataStorage):
    def __init__(self):
        self.server = couchdb.Server(settings.COUCHDB_SERVER)
        self.db = self.server['amqp']

    def __getitem__(self, key):
        try:
            return self.db[key]
        except (couchdb.ResourceNotFound, AttributeError):
            return None

    def __setitem__(self, key, doc):
        self.db[key] = doc

    def __delitem__(self, key):
        del self.db[key]


def get_data_implementor():
    return CachedDataStorage
    try:
        s = couchdb.Server(settings.COUCHDB_SERVER)
        db = s['amqp']
        return CouchDbDataStorage
    except (couchdb.ResourceNotFound, AttributeError):
        return CachedDataStorage


DataStorage = get_data_implementor()

