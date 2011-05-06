from datetime import date, timedelta, datetime
from urllib import quote_plus
import random

from django import template
from django.template.defaultfilters import date as datefilter
from django.conf import settings
from django.forms.widgets import CheckboxInput
from django.core.cache import cache
from django.utils.http import urlquote, urlquote_plus
from django.utils.hashcompat import sha_constructor
from django.utils import simplejson as json
from django.contrib.markup.templatetags.markup import markdown
from django.contrib.sites.models import Site
from django.contrib.flatpages.models import FlatPage

from rdutils.html2text import html2text as h2t
from rdutils.url import POPUP, POPUP_WIDE


register = template.Library()


@register.simple_tag
def domain():
    return Site.objects.get_current().domain


@register.simple_tag
def firstname_or_username(user):
    """Return user's first name if available. Otherwise, return username."""
    return user.first_name or user.username.title()


@register.simple_tag
def popup():
    """Return popup HTML code."""
    return POPUP


@register.simple_tag
def popup_wide():
    """Return popup HTML code."""
    return POPUP_WIDE

@register.inclusion_tag('common/tags/flatpage_fragment.html', takes_context=True)
def common_flatpage(context, url, param1=None, param2=None):
    """Return flatpage body matching the given url."""
    try:
        request = context['request']
        if param1:
            url = url % param1
        if param2:
            url = url + param2
        cache_key = u':'.join(['rv-flatpage', url])
        if not (request.user.is_staff and request.user.is_active):
            content = cache.get(cache_key, None)
        else:
            # Always show uncached content to admin
            content = None
        if content is None:
            page = FlatPage.objects.get(url=url)
            content = markdown(page.content)
            cache.set(cache_key, content, 300)
        return {'content':content}
    except FlatPage.DoesNotExist:
        return {}


@register.inclusion_tag('common/tags/flatpage_fragment.html', takes_context=True)
def common_rotating_flatpage(context, url, param1=None):
    """Return flatpage body randomly matching one of the given urls."""
    try:
        request = context['request']
        if param1:
            url = url % param1
        pages = Site.objects.get_current().flatpage_set.filter(url__startswith=url).values_list("pk", flat=True)
        if not pages:
            return {}
        page_pk = random.choice(pages)
        page = Site.objects.get_current().flatpage_set.get(pk=page_pk)
        content = markdown(page.content)
        return {'content':content}
    except FlatPage.DoesNotExist:
        return {}


@register.inclusion_tag("common/form_fields.html")
def common_formfield_render(field):
    """Render a form field.

    The parameter ``field`` is a bound form field.

    """
    is_checkbox = isinstance(field.field.widget, CheckboxInput)
    label_html = field.label_tag(contents=field.label) # Unescaped label tag
    return {'field':field, 'is_checkbox':is_checkbox, 'label_html':label_html}


@register.inclusion_tag("common/form_fields_mobile.html")
def common_formfield_render_mobile(field):
    """Render a form field.

    The parameter ``field`` is a bound form field.

    """
    is_checkbox = isinstance(field.field.widget, CheckboxInput)
    label_html = field.label_tag(contents=field.label) # Unescaped label tag
    return {'field':field, 'is_checkbox':is_checkbox, 'label_html':label_html}


@register.inclusion_tag("common/form_fields_tr.html")
def common_formfield_render_tr(field):
    """Render a form field.

    The parameter ``field`` is a bound form field.

    """
    is_checkbox = isinstance(field.field.widget, CheckboxInput)
    label_html = field.label_tag(contents=field.label) # Unescaped label tag
    return {'field':field, 'is_checkbox':is_checkbox, 'label_html':label_html}


class CacheNode(template.Node):
    def __init__(self, nodelist, expire_time, fragment_name, vary_on):
        self.nodelist = nodelist
        self.expire_time = expire_time
        self.fragment_name = fragment_name
        self.vary_on = vary_on

    def render(self, context):
        # Build a unicode key for this fragment and all vary-on's.
        cache_key = u':'.join([self.fragment_name] + [urlquote(template.resolve_variable(var, context)) for var in self.vary_on])
        cache_key = sha_constructor(cache_key).hexdigest()
        value = ''
        try:
            value = cache.get(cache_key, None)
            if value is None:
                value = self.nodelist.render(context)
                expire_time = int(template.resolve_variable(self.expire_time, context))
                cache.set(cache_key, value, expire_time)
        except AttributeError: # This is sometimes thrown by memcached.py
            pass
        return value


def do_cache(parser, token):
    """
    This will cache the contents of a template fragment for a given amount
    of time.

    Usage::

        {% tcache [expire_time] [fragment_name] %}
            .. some expensive processing ..
        {% endtcache %}

    This tag also supports varying by a list of arguments::

        {% tcache [expire_time] [fragment_name] [var1] [var2] .. %}
            .. some expensive processing ..
        {% endtcache %}

    Each unique set of arguments will result in a unique cache entry.

    [expire_time] may be a context variable or an integer constant.

    """
    nodelist = parser.parse(('endtcache',))
    parser.delete_first_token()
    tokens = token.contents.split()
    if len(tokens) < 3:
        raise template.TemplateSyntaxError(u"'%r' tag requires at least 2 arguments." % tokens[0])
    expire_time = tokens[1]
    return CacheNode(nodelist, expire_time, tokens[2], tokens[3:])

register.tag('tcache', do_cache)


@register.filter
def truncatestring(value, arg):
    """Truncate a string to the given length"""
    max_length = int(arg)
    if len(value) > max_length:
        return u"%s..." % value[:max_length]
    else:
        return value
truncatestring.is_safe = False


@register.filter
def daysleft(value):
    today = date.today()
    diff = value - today
    if diff.days == 1:
        return "1 day"
    else:
        return "%s days" % diff.days


@register.filter
def std_date(value, format):
    '''Reformat standard date.

    Supported date format example:
        Tue, 19 Dec 2008 21:41:47 +0000

    '''
    try:
        d, dt = value.split(', ')
        dt, d = dt.split(' +')
        dt = datetime.strptime(dt, "%d %b %Y %H:%M:%S")
        return datefilter(dt, format)
    except:
        return value


@register.simple_tag
def mp3_url_player(mp3_url):
    return settings.MP3_URL_PLAYER % {'mp3_url':urlquote(mp3_url)}


_TKT_URL = getattr(settings, 'TICKETMASTER_URL', None)

@register.filter
def referer_url(value):
    """Change TicketMaster URL to a referer URL"""
    if _TKT_URL and value:
        v = value.lower()
        if 'ticketmaster.com' in v or 'ticketweb.com' in v:
            url = _TKT_URL % {'url':quote_plus(value)}
            return url
    return value


@register.filter
def html2text(value):
    v = h2t(value)
    if v:
        v = v.replace('*', '')
    return v


@register.filter
def jsonify(value):
    return json.dumps(value)


@register.inclusion_tag('common/tags/queries.html')
def sql_connections():
    from django.db import connection
    return {'queries':connection.queries}

@register.filter
def urlencode_full(value):
    """Escapes a value for use in a URL."""
    from django.utils.http import urlquote
    return urlquote_plus(value)
urlencode_full.is_safe = False

