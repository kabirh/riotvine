import logging
from sys import exc_info
from traceback import format_exception
import urllib2
from BeautifulSoup import BeautifulSoup as BS
from urlparse import urlparse
from cgi import parse_qs

from django.utils.http import urlquote
from django.utils import simplejson as json
from django.conf import settings

from oembed.models import ServiceProvider
from oembed.providers import registry


_log = logging.getLogger('oembed.utils')


def get_embed_code(service_provider, url, max_width=None, keys=None):
    """Return the oEmbed code for the given url in the form of a dictionary.

    `service_provider` may be an instance of ServiceProvider or a host name.

    `max_width` - maximum width of the embedded media content

    `keys` - response keys as a comma-delimited string
        For example: "width, height, html".
        The return dictionary will always contain these keys.
    """
    req_url = u''
    try:
        if not isinstance(service_provider, ServiceProvider):
            service_provider = ServiceProvider.objects.get(host=service_provider)
        keys = keys or service_provider.keys.split(',')
        max_width = max_width or service_provider.max_width
        url = urlquote(url)
        req_url = '%s?url=%s&maxwidth=%s&format=json' % (service_provider.json_endpoint, url, max_width)
        _log.debug("Request %s", req_url)
        implementation = registry.get(service_provider.host)
        if implementation:
            ret = implementation.get_json(req_url)
        else:
            req = urllib2.Request(req_url)
            req.add_header("User-agent", settings.USER_AGENT)
            resp = urllib2.urlopen(req)
            ret = resp.read()
            resp.close()
        _log.debug("Response %s", ret)
        resp_dict = json.loads(ret)
        if service_provider.service_type != resp_dict.get('type', None):
            return None
        # Extract values for required keys of interest from the response dictionary
        ret_dict= {'service_provider':service_provider}
        for key in keys:
            k = key.strip()
            value = resp_dict[k]
            ret_dict[k] = value
        return ret_dict
    except urllib2.URLError, e:
        reason = u'Unknown'
        if hasattr(e, 'reason'):
            reason = e.reason  
        if hasattr(e, 'code'):
            reason = e.code
        _log.warn("OEmbed request failed (reason: %s) for %s - %s \n%s", reason, service_provider, url, req_url)
        _log.exception(''.join(format_exception(*exc_info())))
        return None
    except:
        _log.warn("OEmbed request failed for %s - %s\n%s", service_provider, url, req_url)
        _log.exception(''.join(format_exception(*exc_info())))
        return None


def get_soundcloud_param_value(embed_code):
    '''Return the 'value' attribute of the param tag whose `name` is 'movie'.
    In this embed code:
        <object height="81" width="100%"> <param name="movie" value="http://player.soundcloud.com/player.swf?url=http%3A%2F%2Fsoundcloud.com%2Fstraydnb%2Fhelios-first-dream-called-ocean-stray-remix"></param> <param name="allowscriptaccess" value="always"></param> <embed allowscriptaccess="always" height="81" src="http://player.soundcloud.com/player.swf?url=http%3A%2F%2Fsoundcloud.com%2Fstraydnb%2Fhelios-first-dream-called-ocean-stray-remix" type="application/x-shockwave-flash" width="100%"></embed> </object>  <span><a href="http://soundcloud.com/straydnb/helios-first-dream-called-ocean-stray-remix">Helios - First Dream Called Ocean (Stray Remix)</a>  by  <a href="http://soundcloud.com/straydnb">straydnb</a></span>
    the return value would be:
        http://soundcloud.com/straydnb/helios-first-dream-called-ocean-stray-remix
        
    If embed code is a direct URL, validate and return it
    
    '''
    try:
        if embed_code.startswith('http'): # direct URL
            value = embed_code
            u = urlparse(value)
            if u.hostname.lower().endswith('soundcloud.com') and u.scheme.lower() in ('http', 'https'):
                return value
            else:
                return None
        html = BS(embed_code)
        p = html.find("param", {'name':'movie'})
        if p:
            value = p.attrMap['value']
            u = urlparse(value)
            if u.hostname.lower().endswith('soundcloud.com'):
                q = u.query # url=http%3A%2F%2Fsoundcloud.com%2Fstraydnb%2Fhelios-first-dream-called-ocean-stray-remix
                parsed = parse_qs(q)
                value = parsed['url'][0]
                u = urlparse(value)
                if u.hostname.lower().endswith('soundcloud.com') and u.scheme.lower() in ('http', 'https'):
                    return value
    except:
        _log.exception(''.join(format_exception(*exc_info())))
    return None
    
    
