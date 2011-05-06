"""

Twitter AMQP tasks

# http://twitter.com/users/show.xml?id=18119959
from twitter.amqp.tasks import *
twitter_id = '18119959' # rookd1
refresh_friends(twitter_id)

"""
import logging
from datetime import datetime
import time
from uuid import uuid4

from django.conf import settings

from twitter.amqp.queues import GetQ, SearchQ
from amqp import DataStorage, aq
from rdutils.cache import shorten_key, cache
from twitter.models import TwitterProfile


_log = logging.getLogger('twitter.amqp.tasks')
_DELIVERY_MODE = getattr(settings, 'AMQP_DELIVERY_MODE', 1)

THRESHOLD_SECONDS = 60*15 # 15 minutes


def refresh_friends(twitter_id, queue=None, extra_headers=None, access_token=''):
    """Refresh friends of the given twitter user_id.

    The AMQP chain of functions is:

        1. twitter/twitter.get.get_followers (replies to: 2 with next reply to: 3)
        2. twitter/twitter.get.get_followees (replies to: 3 with next reply to: 4)
        3. twitter/twitter.compute.get_friends (replies to: 4 with next reply to: None)
        4. twitter/twitter.compute.save_friends (replies to: final_reply_to/None with next reply to: None)

    """
    try:
        kx = u"" # uuid4().hex
        correlation_id = shorten_key('twitter_refresh_friends:%s:%s' % (twitter_id, kx))
        ds = DataStorage()
        val = ds[correlation_id]
        if val is not None:
            if (time.time() - val['timestamp']) > THRESHOLD_SECONDS:
                del ds[correlation_id] # clear out zombie data
            else:
                _log.debug("Another worker is refreshing friends for twitter_id %s", twitter_id)
                return
        ds[correlation_id] = {'timestamp':time.time()}
        app_headers = {
            'twitter_id':twitter_id,
            'access_token':access_token,
        }
        if extra_headers:
            app_headers.update(extra_headers)
        msg = aq.Message(
            '',
            delivery_mode=_DELIVERY_MODE,
            correlation_id=correlation_id,
            application_headers=app_headers,
            reply_to='twitter/twitter.get.get_followees'
        )
        q = queue or GetQ(bind_queue=False)
        q.send(msg, q.exchange_name, 'twitter.get.get_followers')
        ds.close()
        _log.debug("Friend refresh initiated for twitter_id %s", twitter_id)
    except Exception, e:
        _log.debug("Could not refresh friends for twitter_id %s", twitter_id)
        _log.exception(e)


def build_friends(queue=None):
    q = queue or GetQ(bind_queue=False)
    tx = TwitterProfile.objects.active().values_list('appuser_id', 'access_token')
    for twitter_id, access_token in tx:
        refresh_friends(twitter_id, queue=q, access_token=access_token)


def search(twitter_id, params, object_type='', reply_to=None, queue=None, extra_headers=None, high_priority=False):
    """Twitter Search"""
    try:
        q = params.get('q', u'')
        key_prefix = high_priority and u'amqp.twitter.priosearch' or u'amqp.twitter.search'
        key = shorten_key(u'%s:%s:%s:%s' % (key_prefix, object_type, twitter_id, q))
        tstamp = cache.cache.get(key, None)
        if tstamp:
            _log.debug("Skipping already queued Twitter search for %s %s", object_type, twitter_id)
            return # this twitter search is already in the queue; don't requeue it
        headers = {'twitter_id':twitter_id, 'object_type':object_type}
        if extra_headers:
            headers.update(extra_headers)
        headers['cache_key'] = key
        correlation_id = uuid4().hex
        ds = DataStorage()
        ds[correlation_id] = {'timestamp':time.time()}
        msg = aq.Message(
            params,
            content_type='application/json',
            delivery_mode=_DELIVERY_MODE,
            correlation_id=correlation_id,
            timestamp=datetime.now(),
            application_headers=headers,
            reply_to=reply_to
        )
        q = queue or SearchQ(bind_queue=False)
        routing_key = high_priority and 'twitter.priosearch.search' or 'twitter.search.search'
        cache.cache.set(key, int(time.time()), 3600*5)
        q.send(msg, q.exchange_name, routing_key)
        ds.close()
        _log.debug("Twitter search initiated for twitter_id %s. High prio: %s", twitter_id, high_priority)
    except Exception, e:
        _log.error("Could not initiate Twitter search for twitter_id %s. High prio: %s", twitter_id, high_priority)
        _log.exception(e)

