import os
import mimetypes

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from django.conf import settings
from django.core.files.base import File
from django.core.files.storage import Storage
from django.utils.functional import curry
from django.core.exceptions import ImproperlyConfigured

from rdutils.cache import key_suffix, short_key, clear_keys, cache

try:
    from boto.s3.connection import S3Connection
    from boto.s3.key import Key
except ImportError:
    raise ImproperlyConfigured, "Could not load Boto's S3 bindings.\
    \nSee http://code.google.com/p/boto/"

ACCESS_KEY_NAME = 'AWS_ACCESS_KEY_ID'
SECRET_KEY_NAME = 'AWS_SECRET_ACCESS_KEY'
HEADERS         = 'AWS_HEADERS'
BUCKET_NAME     = 'AWS_STORAGE_BUCKET_NAME'
DEFAULT_ACL     = 'AWS_DEFAULT_ACL'
QUERYSTRING_EXPIRE = 'AWS_QUERYSTRING_EXPIRE'

BUCKET_PREFIX     = getattr(settings, BUCKET_NAME, "root")
HEADERS           = getattr(settings, HEADERS, {})
DEFAULT_ACL       = getattr(settings, DEFAULT_ACL, 'public-read')
QUERYSTRING_EXPIRE= getattr(settings, QUERYSTRING_EXPIRE, 3600)


class S3BotoStorage(Storage):
    """Amazon Simple Storage Service using Boto"""
    
    def __init__(self, bucket="", bucketprefix=BUCKET_PREFIX, 
            access_key=None, secret_key=None, acl=DEFAULT_ACL, headers=HEADERS):
        self.acl = acl
        self.headers = headers
        
        if not access_key and not secret_key:
             access_key, secret_key = self._get_access_keys()
        
        self.connection = S3Connection(access_key, secret_key, is_secure=False)
        self.bucket = self.connection.create_bucket(bucketprefix + bucket)
        self.bucket.set_acl(self.acl)
    
    def _get_access_keys(self):
        access_key = getattr(settings, ACCESS_KEY_NAME, None)
        secret_key = getattr(settings, SECRET_KEY_NAME, None)
        if (access_key or secret_key) and (not access_key or not secret_key):
            access_key = os.environ.get(ACCESS_KEY_NAME)
            secret_key = os.environ.get(SECRET_KEY_NAME)
        
        if access_key and secret_key:
            # Both were provided, so use them
            return access_key, secret_key
        
        return None, None
    
    def _open(self, name, mode='rb'):
        name = name.replace("\\", "/")
        return S3BotoStorageFile(name, mode, self)
    
    def _save(self, name, content):
        name = name.replace("\\", "/")
        headers = self.headers
        try:
            headers['Content-Type'] =  content.content_type # content.file.content_type
        except AttributeError:
            headers['Content-Type'] = mimetypes.guess_type(name)[0] or "application/x-octet-stream"
        k = self.bucket.get_key(name)
        if not k:
            k = self.bucket.new_key(name)
        k.set_contents_from_file(content, headers=headers, policy=self.acl)
        return name
    
    def delete(self, name):
        name = name.replace("\\", "/")
        self.bucket.delete_key(name)
    
    def exists(self, name):
        name = name.replace("\\", "/")
        k = Key(self.bucket, name)
        return k.exists()
    
    def listdir(self, name):
        name = name.replace("\\", "/")
        return [l.name for l in self.bucket.list() if not len(name) or l.name[:len(name)] == name]
    
    def size(self, name):
        name = name.replace("\\", "/")
        key = u"s3_size:%s" % name
        key = short_key(key)
        value = cache.cache.get(key, None)
        if value is None:
            kx = self.bucket.get_key(name)
            value = kx and kx.size or 0
            cache.cache.set(key, value, 3600*24*30)
        return value

    def url(self, name):
        name = name.replace("\\", "/")
        key = u"s3_url:%s" % name
        key = short_key(key)
        value = cache.cache.get(key, None)
        if value is None:
            value = self.bucket.get_key(name).generate_url(QUERYSTRING_EXPIRE, method='GET', force_http=True)
            cache.cache.set(key, value, 3600*24*30)
        return value

    def get_available_name(self, name):
        """ Overwrite existing file with the same name. """
        name = name.replace("\\", "/")
        return name


class S3BotoStorageFile(File):
    def __init__(self, name, mode, storage):
        name = name.replace("\\", "/")
        self._storage = storage
        self._name = name
        self._mode = mode
        self.key = storage.bucket.get_key(name)
        if not self.key:
            self.key = storage.bucket.new_key(name)
        self.key.BufferSize = 4000000
        self.file = StringIO()
        self.file_populated = False
    
    def size(self):
        return self.key.size
    
    def read(self, *args, **kwargs):
        # data = self.key.read(*args, **kwargs)
        if not self.file_populated:
            for d in self.key:
                self.file.write(d)
            self.file_populated = True
        return self.file.getvalue()
        # return data
    
    def write(self, content):
        self.key.set_contents_from_string(content, headers=self._storage.headers, acl=self._storage.acl)
        self.file = StringIO(content)
        self.file_populated = True
    
    def close(self):
        self.key.close()
        self.file.close()

