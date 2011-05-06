import logging
import re
import urlparse, cgi

from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe
from django.utils.html import urlize

from rdutils.query import get_or_none
from rdutils.cache import key_suffix, short_key, clear_keys, cache
from twitter.utils import get_tweets_by_hashtag


_log = logging.getLogger("twitter.templatetags.twittertags")

register = template.Library()


@register.simple_tag
def twitter_profile_url(user):
    """Return Twitter profile URL for the given user"""
    from twitter.models import TwitterProfile
    sfx = key_suffix(u'twitter_profile', user.pk)
    key = short_key(u'twitter_profile_url:%s' % sfx)
    value = cache.cache.get(key, None)
    if value is None:
        p = get_or_none(TwitterProfile.objects.active(), user_profile__user__pk=user.pk)
        if p:
            value = u'http://twitter.com/%s' % p.screen_name
        else:
            value = user.get_profile().get_absolute_url()
        cache.cache.set(key, value)
    return value


@register.inclusion_tag('twitter/tags/tweets.html')
def tweets_by_hashtag(hashtag, limit=25):
    """Return tweets by hashtag"""
    tweets = get_tweets_by_hashtag(hashtag)
    return {
        'qtype':'hashtag',
        'term':hashtag,
        'tweets':tweets
    }


@register.filter
def twitter_q(value):
    """Enclose phrases into double quotes for exact Twitter search"""
    if value:
        value = value.strip()
        if (' ' in value or '+' in value) and '"' not in value:
            return u'"%s"' % value
    return value
twitter_q.is_safe = True

'''
# j; JPEG
# p; PNG
# b; BMP
# t; TIFF
# g; GIF
# s; SWF
# d; PDF
# f; FLV
# z; MP4 
'''
_YFROG_SUFFIXES = list('jpbtgfz')

@register.filter
@stringfilter
def twitterize(value, autoescape=None):
    # twitpic / twitvid/ yfrog support
    append = u''
    try:
        v = value.lower()
        if 'http://twitpic.com/' in v or \
                'http://yfrog.com/' in v or \
                'http://twitvid.com/' in v or \
                'youtube.com/watch?' in v:
            for w in value.split():
                wx = w.lower()
                if wx.startswith('http://twitpic.com/'):
                    img_id = w.split('/')[-1]
                    append = append + u'<a href="%s"><img src="http://twitpic.com/show/mini/%s"/></a>' % (w, img_id)
                elif wx.startswith('http://yfrog.com/') and w[-1] in _YFROG_SUFFIXES:
                    img_id = w
                    append = append + u'<a href="%s"><img src="%s.th.jpg"/></a>' % (w, img_id)
                elif wx.startswith('http://twitvid.com/'):
                    img_id = w.split('/')[-1]
                    append = append + u'''<object width="425" height="344">
                         <param name="movie" value="http://www.twitvid.com/player/%s>"></param>
                         <param name="allowFullScreen" value="true"></param>
                         <embed type="application/x-shockwave-flash" src="http://www.twitvid.com/player/%s" 
                            quality="high" allowscriptaccess="always" allowNetworking="all"     
                            allowfullscreen="true" wmode="transparent" height="344" width="425"></embed>
                         </object>''' % (img_id, img_id)
                elif wx.startswith('http://youtube.com/') or wx.startswith('http://www.youtube.com/'):
                    # Example URL: http://www.youtube.com/watch?v=Apadq9iPNxA
                    pieces = urlparse.urlsplit(w)
                    img_id = cgi.parse_qs(pieces.query)['v'][0]
                    append = append + u'''<object width="425" height="344">
                        <param name='movie' value='http://www.youtube.com/v/%s&hl=en&fs=1'></param>
                        <param name='allowFullScreen' value='true'></param>
                        <embed src='http://www.youtube.com/v/%s&hl=en&fs=1' 
                            type='application/x-shockwave-flash' allowfullscreen='true' 
                            height="344" width="425"></embed>
                        </object>''' % (img_id, img_id)
    except:
        pass
	# Link URLs
    value = urlize(value, nofollow=False, autoescape=autoescape)
	# Link twitter usernames prefixed with @
    value = re.sub(r'(\s+|\A)@([a-zA-Z0-9\-_]*)\b',r'\1<a href="http://twitter.com/\2">@\2</a>',value)
	# Link hash tags
    value = re.sub(r'(\s+|\A)#([a-zA-Z0-9\-_]*)\b',r'\1<a href="http://search.twitter.com/search?q=%23\2">#\2</a>',value)
    if append:
        value = value + u'<br/>' + append
    return mark_safe(value)
twitterize.is_safe=True
twitterize.needs_autoescape = True

