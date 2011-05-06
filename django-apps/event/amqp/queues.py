import logging
import time
from amqplib.client_0_8 import Message

from django.conf import settings
from amqp import AbstractQueue, DataStorage

from event import utils


_log = logging.getLogger('event.amqp.queues')


__all__ = ('eventsq', 'EventsQ')


class EventsQ(AbstractQueue):
    exchange_name = 'signal'
    delivery_mode = getattr(settings, 'AMQP_DELIVERY_MODE', 1)
    queue_name = 'events'
    routing_key = 'signal.events.#'
    stop_routing_key = 'signal.events.stop'

    def build_recommended_events(self, msg, hdrs, next):
        utils.build_recommended_events(hdrs['user_profile_id'])
        return None

    def recommend_event_to_friends(self, msg, hdrs, next):
        utils.recommend_event_to_friends(hdrs['user_profile_id'], hdrs['event_id'])
        return None

    def send_event_reminder(self, msg, hdrs, next):
        utils.send_event_reminder(msg.body)
        return None
    
    def save_event_tweets(self, msg, hdrs, next):
        event_id = hdrs['twitter_id']
        do_reset = hdrs.get('do_reset', False)
        ds = DataStorage()
        data = ds[msg.correlation_id]
        if data is None:
            data = {'results': []}
        if data and 'results' in data:
            tweets = data['results']
            del ds[msg.correlation_id]
            ds.close()
            # if tweets or do_reset:
            utils.save_event_tweets(event_id, tweets, do_reset)
            _log.debug("Saved %s tweets for event %s", len(tweets), event_id)
            return None


eventsq = EventsQ

