from django.conf import settings
from django.core.cache import cache
from messages.models import inbox_count_for


def messages(request):
    """Add context variables related to ``messages`` app"""
    count = 0
    ctx = {}
    if request.user.is_authenticated():
        key = 'message-count-%s' % request.user.pk
        #count = cache.get(key)
        count = None
        if count is None:
            count = inbox_count_for(request.user)
            cache.set(key, count)
    ctx['UNREAD_MESSAGE_COUNT'] = count
    return ctx


