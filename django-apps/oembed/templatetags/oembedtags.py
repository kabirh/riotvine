import logging
import time

from django import template
from django.conf import settings
from django.core.cache import cache
from django.utils.http import urlquote 

from oembed import utils


_log = logging.getLogger('oembed.templatetags.oembedtags')

register = template.Library()


class OEmbedNode(template.Node):
    def __init__(self, host, url):
        self.host = host
        self.url = url

    def render(self, context):
        host = template.resolve_variable(self.host, context)
        url = template.resolve_variable(self.url, context)
        cache_key = u':'.join(['oembed', urlquote(url)])
        value = cache.get(cache_key)
        if value is None:
            ctx = utils.get_embed_code(host, url)
            if ctx is None:
                # retry once
                time.sleep(.125)
                ctx = utils.get_embed_code(host, url)                
            if ctx:
                ctx['host'] = ctx['service_provider'].host.replace('.', '-')
                ctx['url'] = url
                tpl = [u'oembed/tags/type_%s.html' % ctx['service_provider'].service_type]
                value = template.loader.select_template(tpl).render(template.Context(ctx))
                cache.set(cache_key, value, 24*3600)
            else:
                value = ''
                cache.set(cache_key, value, 180) # Stop retrying for a few minutes
        return value


def do_oembed(parser, token):
    """Render an oEmbedded resource.

    Usage::

        {% oembed [host] [url] %}

    """
    tokens = token.contents.split()
    if len(tokens) != 3:
        raise template.TemplateSyntaxError(u"'%r' tag requires exactly 2 arguments." % tokens[0])
    host = tokens[1]
    url = tokens[2]
    return OEmbedNode(host, url)

register.tag('oembed', do_oembed)

