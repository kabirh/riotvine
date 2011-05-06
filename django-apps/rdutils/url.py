import logging
import urllib, urllib2
import time

from django.conf import settings
from django.core.cache import cache
from django.db.models import Model
from django.utils.safestring import mark_safe
from django.utils import simplejson as json
from django.utils.encoding import iri_to_uri

from rdutils.cache import shorten_key
from rdutils.query import get_or_none
from common.models import KeyValue


POPUP = '''onclick="window.open(this.href, 'popupwindow', 'width=800,height=630,scrollbars=1,resizable=1,menubar=1,location=yes');return false;"
              onkeypress="window.open(this.href, 'popupwindow', 'width=800,height=630,scrollbars=1,resizable=1,menubar=1,location=yes');return false;"'''

POPUP_WIDE = '''onclick="window.open(this.href, 'popupwindow', 'width=1000,height=630,scrollbars=1,resizable=1,menubar=1,location=yes');return false;"
              onkeypress="window.open(this.href, 'popupwindow', 'width=1000,height=630,scrollbars=1,resizable=1,menubar=1,location=yes');return false;"'''

_log = logging.getLogger('rdutils.url')


def admin_url(obj, verbose_name=None):
    """Dispatch to the appropriate instance or class method."""
    if isinstance(obj, Model):
        return admin_url_for_object(obj, verbose_name)
    else:
        return admin_url_for_class(obj, verbose_name)


def admin_url_for_object(instance, verbose_name=None):
    """Return admin detail URL for the given model instance."""
    app_label = instance.__class__._meta.app_label
    model_name = instance.__class__.__name__.lower()
    if not verbose_name:
        verbose_name = unicode(instance.__class__._meta.verbose_name).title()
        verbose_name = '%s: %s' % (verbose_name, unicode(instance))
    return mark_safe('<a href="%s/%s/%s/%s/">%s</a>' % (
                        settings.ADMIN_BASE,
                        app_label,
                        model_name,
                        instance.pk,
                        verbose_name))


def admin_url_for_class(model_class, verbose_name=None):
    """Return admin list URL for the given model class."""
    app_label = model_class._meta.app_label
    model_name = model_class.__name__.lower()
    if not verbose_name:
        verbose_name = unicode(model_class._meta.verbose_name_plural).title()
    return mark_safe('<a href="%s/%s/%s/">%s</a>' % (
                        settings.ADMIN_BASE,
                        app_label,
                        model_name,
                        verbose_name))


def call_view_class(request, *args, **kwargs):
    """Instantiate and call a class-based view.

    This ensures that the class is instantiated per request. Typical use is 
    in conjunction with FormPreview and FormWizard.

    """
    cls = kwargs.pop('class')
    return cls(request=request)(request, *args, **kwargs)


'''bit.ly response sample:
{ "errorCode": 0,
  "errorMessage": "", 
  "results": 
    { "http://illiusrock.com": 
       { "hash": "13S8a", "shortKeywordUrl": "", 
         "shortUrl": "http://bit.ly/LTs8y", "userHash": "LTs8y" } }, 
  "statusCode": "OK" }
'''
def get_tiny_url(url):
    tiny_link = None
    d = u''
    params = u''
    try:
        key = shorten_key(u'tiny-%s' % url)
        tiny_link = cache.get(key, None)
        if tiny_link is None:
            tiny_link = get_or_none(KeyValue.objects, key=url, category='tinyurl')
            if tiny_link:
                tiny_link = tiny_link.value
            if tiny_link is None:
                tiny_url_api = getattr(settings, 'TINY_URL_API', 'http://tinyurl.com/api-create.php')            
                if "bit.ly" in tiny_url_api:
                    params = {
                        'longUrl':url,
                        'login':settings.BITLY_API_LOGIN,
                        'apiKey':settings.BITLY_API_KEY,
                        'version':getattr(settings, 'BITLY_API_VERSION', '2.0.1'),
                        'format':'json',
                    }
                else:
                    params = {'url':url}
                data = urllib.urlencode(params)            
                tiny_link = urllib2.urlopen(tiny_url_api, data).read().strip()
                if "bit.ly" in tiny_url_api:
                    d = json.loads(tiny_link)
                    if not d:
                        return url
                    tiny_link = d['results'][url]['shortUrl']
                if len(tiny_link) > 25:
                    return url
                KeyValue.objects.get_or_create(key=url, category='tinyurl', defaults=dict(value=tiny_link))
            cache.set(key, tiny_link, 3600 * 12)
        return tiny_link
    except Exception, e:        
        _log.exception(e)
        _log.warning("Failed to get short URL for %s\nwith error: %s\nd=%s\nparams=%s", url, e, d, params)
        return tiny_link or url


def test_url(url, search_string, error_value=False):
    """Return True if the page at a URL contains a search string. Otherwise, return error_value."""
    try:
        _log.debug("Testing url %s: %s", url, search_string)
        req = urllib2.Request(url)
        req.add_header('User-Agent',  settings.USER_AGENT)
        req.add_header('Referer', 'http://%s/' % settings.DISPLAY_SITE_DOMAIN)
        resp = urllib2.urlopen(req)        
        ret = resp.read()
        resp.close()
        time.sleep(0.2) # throttle at 5 requests/second max to be kind to others
        return search_string in ret.decode('utf-8')
    except Exception, e:
        _log.debug("URL %s returned error %s", url, e)
        return error_value


def download_url(url):
    """Return content downloaded from a URL"""
    try:
        _log.debug("Downloading url %s", url)
        req = urllib2.Request(url)
        req.add_header('User-Agent',  settings.USER_AGENT)
        req.add_header('Referer', 'http://%s/' % settings.DISPLAY_SITE_DOMAIN)
        resp = urllib2.urlopen(req)
        ret = resp.read()
        resp.close()
        time.sleep(0.2) # throttle at 5 requests/second max to be kind to others
        return ret # .decode('utf-8')
    except Exception, e:
        _log.debug("Couldn't download URL %s\nError: %s", url, e)
        return None


def sanitize_url(url):
    """URL quote the query string part of this URL then convert with IRI to URI"""
    return iri_to_uri(url)

