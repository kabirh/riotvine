"""

# ---
from twitter.amqp.queues import *
getq = GetQ()
getq.listen()

# ---
from twitter.amqp.queues import *
compq = ComputeQ()
compq.listen()

# ---
from twitter.amqp.queues import *
from amqp import *
import time

correlation_id = 'my_corr2_id'
ds = DataStorage()
del ds[correlation_id]
ds[correlation_id] = {'timestamp':time.time()}


connection = get_connection()
channel = connection.channel()
channel.access_request('/data', active=True, read=True, write=True)
exchange = 'twitter'
routing_key = 'twitter.get.get_followers'
twitter_id = '18119959'
reply_to = 'twitter/twitter.get.get_followees'
msg = aq.Message(
    '',
    delivery_mode=2,
    content_type='text/plain',
    correlation_id=correlation_id,
    application_headers={
        'twitter_id':twitter_id,
    },
    reply_to=reply_to,
)
ds[correlation_id] = {}
channel.basic_publish(msg, exchange, routing_key=routing_key)

friends = [26177586, 2206131, 9720292, 14337870]

"""
import logging
from datetime import datetime, timedelta
import time
from amqplib.client_0_8 import Message

from django.conf import settings
from django.db import transaction
from django.db.models import F, Q

from rdutils.cache import get_cache_key_suffix, shorten_key, clear_cached_keys, cache
from amqp import AbstractQueue, DataStorage
from twitter import utils
from twitter.models import TwitterFriend, TwitterProfile
from registration.models import UserProfile, Friendship


_log = logging.getLogger('twitter.amqp.queues')


__all__ = ('GetQ', 'ComputeQ', 'SearchQ', 'PrioritySearchQ', 'getq', 'computeq', 'searchq', 'priosearchq')


class TwitterQ(AbstractQueue):
    exchange_name = 'twitter'
    delivery_mode = getattr(settings, 'AMQP_DELIVERY_MODE', 1)

    def call_fn(self, fn, msg, hdrs, next):
        return fn(hdrs.get('twitter_id', '0'), msg, hdrs, next, msg.correlation_id)


class SearchQ(TwitterQ):
    queue_name = 'twitter_search'
    routing_key = 'twitter.search.#'
    stop_routing_key = 'twitter.search.stop'

    def search(self, twitter_id, msg, hdrs, next, correlation_id):
        cache_key = hdrs.get('cache_key', None)
        if cache_key:
            cache.cache.delete(cache_key)
        ts = msg.properties.get('timestamp', None)
        if ts and ts < (datetime.now() - timedelta(seconds=3600*5)):
            _log.debug("Skipping stale search request for id %s", twitter_id)
            return None # Don't process stale requests
        params = msg.body
        tweets = utils.search(params)
        _log.debug("Found %s tweets for %s\n%s", len(tweets), twitter_id, msg.properties)
        ds = DataStorage()
        data = ds[correlation_id]
        if data is None:
            data = {'timestamp':time.time()}
        data['results'] = tweets
        data['timestamp'] = time.time()
        ds[correlation_id] = data
        ds.close()
        _log.debug("Sending search results for %s to %s", twitter_id, next)
        if next:
            hdrs['next'] = next
            reply = Message(
                '',
                delivery_mode=self.delivery_mode,
                content_type='text/plain',
                correlation_id=correlation_id,
                application_headers=hdrs,
                reply_to=None,
            )
            return reply
        return None


class PrioritySearchQ(SearchQ):
    queue_name = 'twitter_priosearch'
    routing_key = 'twitter.priosearch.#'
    stop_routing_key = 'twitter.priosearch.stop'

    def search(self, twitter_id, msg, hdrs, next, correlation_id):
        return super(PrioritySearchQ, self).search(twitter_id, msg, hdrs, next, correlation_id)


class GetQ(TwitterQ):
    queue_name = 'twitter_get'
    routing_key = 'twitter.get.#'
    # No need for this queue to be exclusive since we run this on multiple servers now
    # exclusive = True # ensure all Twitter GET calls go through a single throttled funnel
    stop_routing_key = 'twitter.get.stop'

    def get_followers(self, twitter_id, msg, hdrs, next, correlation_id):
        access_token = hdrs.get('access_token', '')
        followers = utils.get_followers(twitter_id, access_token=access_token)
        ds = DataStorage()
        data = ds[correlation_id]
        if data is None:
            data = {}
        data['followers'] = followers
        data['timestamp'] = time.time()
        ds[correlation_id] = data
        ds.close()
        if next:
            hdrs['next'] = next
            reply = Message(
                '',
                delivery_mode=self.delivery_mode,
                content_type='text/plain',
                correlation_id=correlation_id,
                application_headers=hdrs,
                reply_to='twitter/twitter.compute.get_friends', # the function will be asked to send its reply here
            )
            return reply # this will be sent to the exchange/queue to which next points
        return None

    def get_followees(self, twitter_id, msg, hdrs, next, correlation_id):
        access_token = hdrs.get('access_token', '')
        followees = utils.get_followees(twitter_id, access_token=access_token)
        ds = DataStorage()
        data = ds[correlation_id]
        if data is None:
            _log.debug("Followee data lost. Skipping friendship computation for twitter_id %s", twitter_id)
            return None
        data['followees'] = followees
        data['timestamp'] = time.time()
        ds[correlation_id] = data
        ds.close()
        if next:
            hdrs['next'] = next
            reply = Message(
                '',
                delivery_mode=self.delivery_mode,
                content_type='text/plain',
                correlation_id=correlation_id,
                application_headers=hdrs,
                reply_to='twitter/twitter.compute.save_friends',  # the function will be asked to send its reply here
            )
            return reply # this will be sent to the exchange/queue to which next points
        return None


class ComputeQ(TwitterQ):
    queue_name = 'twitter_compute'
    routing_key = 'twitter.compute.#'
    stop_routing_key = 'twitter.compute.stop'

    @transaction.commit_on_success
    def _save_twitter_friends(self, tw_profiles, friends):
        for tw_profile in tw_profiles:
            tw_friends = tw_profile.twitterfriend_set
            tw_friends.all().delete()
            for friend_id in friends:
                tw_friends.create(friend_id=friend_id)

    def get_friends(self, twitter_id, msg, hdrs, next, correlation_id):
        ds = DataStorage()
        data = ds[correlation_id]
        if data is None:
            _log.debug("Follower/Followee data lost. Skipping friendship computation for twitter_id %s", twitter_id)
            return None
        if 'followers' not in data or 'followees' not in data:
            _log.debug("Follower/Followee data unavailable. Skipping friendship computation for twitter_id %s", twitter_id)
            del ds[correlation_id]
            ds.close()
            return None
        followers = data['followers']
        followees = data['followees']
        del ds[correlation_id]
        ds.close()
        try:
            tw_profiles = TwitterProfile.objects.active().filter(appuser_id=unicode(twitter_id)).order_by('-pk')
            tw_profile = tw_profiles[:1].get()
        except TwitterProfile.DoesNotExist:
            return None
        friends = utils.get_friends(twitter_id, followees, followers)
        _log.debug("Twitter friends %s...", list(friends)[:5])
        self._save_twitter_friends(tw_profiles, friends)
        if next:
            hdrs['next'] = next
            reply = Message(
                '',
                delivery_mode=self.delivery_mode,
                content_type='text/plain',
                correlation_id=correlation_id,
                application_headers=hdrs,
                reply_to=None,
            )
            return reply # this will be sent to the exchange/queue to which next points
        return None

    @transaction.commit_on_success
    def _save_site_friends(self, user_profile, twitter_friends):
        # Friendship.objects.filter(Q(user_profile1=user_profile) | Q(user_profile2=user_profile), source='twitter').delete()
        clear_cached_keys('friends', user_profile.pk)
        for fr in twitter_friends:
            Friendship.objects.make_friends(user_profile, fr.user_profile, source='twitter')
        _log.debug("Friends saved for %s", user_profile)

    def save_friends(self, twitter_id, msg, hdrs, next, correlation_id):
        tw_profiles = TwitterProfile.objects.active().filter(appuser_id=unicode(twitter_id))
        if not tw_profiles:
            return None
        tw_profile = tw_profiles[0]
        t2 = TwitterFriend._meta.db_table
        twitter_friends = TwitterProfile.objects.active().extra(
            tables=[t2],
            where=['appuser_id=%s.friend_id' % t2, '%s.twitter_profile_id=%%s' % t2],
            params=[tw_profile.pk]
        ).distinct()
        _log.debug("Twitter friends: %s", twitter_friends[:15])
        for p in tw_profiles:
            self._save_site_friends(p.user_profile, twitter_friends)
        final_reply_to = hdrs.get('final_reply_to', next)
        if final_reply_to:
            hdrs['next'] = final_reply_to
            hdrs['user_profile_id'] = tw_profile.user_profile.pk
            reply = Message(
                '',
                delivery_mode=self.delivery_mode,
                content_type='text/plain',
                correlation_id=correlation_id,
                application_headers=hdrs,
                reply_to=None,
            )
            return reply # this will be sent to the exchange/queue to which next points
        return None


searchq = SearchQ
priosearchq = PrioritySearchQ
getq = GetQ
computeq = ComputeQ

