"""

Custom OEmbed providers for services that don't yet have their own official end points.

"""
import logging
import urlparse, cgi

from django import template
from django.utils.encoding import smart_str


_log = logging.getLogger('oembed.providers')


class OEmbedRegistry(object):
    def __init__(self):
        self.registry = {}

    def register(self, provider, host=None):
        if not host:
            host = provider.host
        self.registry[host.lower()] = provider

    def unregister(self, host):
        try:
            del self.registry[host.lower()]
        except KeyError:
            pass

    def get(self, host):
        return self.registry.get(host.lower(), None)


class OEmbedProvider(object):
    """Abstract base class that is extended by custom OEmbed service providers."""
    provider = None # a subclass must set this
    host = None # a subclass must set this
    aspect = 1 # a subclass must set this

    def get_json(self, url):
        kwargs = self.parse_params(url)
        context = self.get_response(**kwargs)
        return self.render_json_response(context)

    def get_response(self, url, maxwidth, **kwargs):
        """Subclasses must extend this method.

        The method must return a dictionary that will then be passed on 
        to the template `oembed/tags/host_<host>.json`

        """
        height = int(int(maxwidth)/self.aspect)
        context = {'height':height, 'width':maxwidth}
        return context

    def parse_params(self, url):
        query = urlparse.urlsplit(url).query
        query_dict = cgi.parse_qs(query)
        ret_dict = {}
        for k,v in query_dict.iteritems():
            ret_dict[smart_str(k)] = v[0]
        return ret_dict

    def render_json_response(self, context):
        context['provider'] = self.provider
        tpl = [u'oembed/tags/host_%s.json' % self.host.lower().replace('.', '_')]
        return template.loader.select_template(tpl).render(template.Context(context))


class YouTubeProvider(OEmbedProvider):
    provider = 'YouTube'
    host = 'youtube.com'
    aspect = 425.0/344

    def get_response(self, url, maxwidth, **kwargs):
        # Parse URL which will itself have a query string.
        # Extract the value of the `v` parameter which points to 
        # the YouTube video we are interested in.
        #
        # Sample URL:
        #   http://www.youtube.com/watch?v=Apadq9iPNxA
        #
        context = super(YouTubeProvider, self).get_response(url, maxwidth)
        pieces = urlparse.urlsplit(url)
        if self.host.lower() not in pieces.hostname.lower():
            return None
        query2 = pieces.query
        query_dict2 = cgi.parse_qs(query2)
        video_code = query_dict2['v'][0]
        context['video_code'] = video_code
        return context


class MySpaceProvider(OEmbedProvider):
    provider = 'MySpace'
    host = 'myspace.com'
    aspect = 430.0/346

    def get_response(self, url, maxwidth, **kwargs):
        # Parse URL which will itself have a query string.
        # Extract the value of the `videoid` parameter which points to 
        # the MySpace video we are interested in.
        #
        # Sample URL:
        #   http://myspacetv.com/index.cfm?fuseaction=vids.individual&videoid=27687089
        #
        context = super(MySpaceProvider, self).get_response(url, maxwidth)
        pieces = urlparse.urlsplit(url)
        if self.host.lower() not in pieces.hostname.lower():
            return None
        query2 = pieces.query
        query_dict2 = cgi.parse_qs(query2)
        query_dict_norm = {} # dictionary with lowercase keys
        for k,v in query_dict2.iteritems():
            query_dict_norm[k.lower()] = v[0]
        video_code = query_dict_norm['videoid']
        context['video_code'] = video_code
        return context


registry = OEmbedRegistry()
registry.register(YouTubeProvider())
registry.register(MySpaceProvider())

