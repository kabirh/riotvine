"""

Base class for AMQP Queues.

for key, val in msg.properties.items():
    print '%s: %s' % (key, str(val))
for key, val in msg.delivery_info.items():
    print '> %s: %s' % (key, str(val))

application_headers: {u'foo': 7, u'bar': 'baz'}
delivery_mode: 2
content_type: text/plain
> exchange: myfan
> consumer_tag: amq.ctag-4udG/vt/JOvZ+VAGeBMuVg==
> routing_key: twitter.friends
> redelivered: False
> delivery_tag: 1
> channel: <amqplib.client_0_8.channel.Channel object at 0x00BEE630>

"""
import logging

from django.conf import settings
from django.utils import simplejson as json
from django.db import DatabaseError, connection, transaction
from django.core.cache import cache


_PENDING_QUEUE_TIMEOUT = getattr(settings, 'AMQP_PENDING_QUEUE_TIMEOUT', 5*24*3600)


def _x():
  return logging.getLogger('amqp.base')


class AbstractQueue(object):
    QUIT_MESSAGE = 'quit!'
    # Base classes must set these:
    exchange_name = None
    queue_name = None
    routing_key = None
    delivery_mode = getattr(settings, 'AMQP_DELIVERY_MODE', 1)
    # Optional parameters:
    exchange_type = 'topic'
    durable = True
    auto_delete = False
    no_ack = False
    exclusive = False
    blocking = True # determines if a callback is registered or not

    def __init__(self, connection=None, bind_queue=True):
        from amqp import get_connection
        if not connection:
            connection = get_connection()
            # hold on to this connection since it was created here
            self.connection = connection
        else:
            self.connection = None
        channel = connection.channel()
        channel.access_request('/data', active=True, read=True, write=True)
        self.channel = channel
        if bind_queue:
            channel.exchange_declare(self.exchange_name, self.exchange_type, auto_delete=self.auto_delete, durable=self.durable)
            self.qname, _, _ = channel.queue_declare(queue=self.queue_name, exclusive=self.exclusive, durable=self.durable, auto_delete=self.auto_delete)
            channel.queue_bind(self.qname, self.exchange_name, routing_key=self.routing_key)
            if self.blocking:
                channel.basic_consume(self.qname, callback=self.callback, no_ack=self.no_ack)
            _x().debug("Bound to Q %s at %s/%s", self.qname, self.exchange_name, self.routing_key)

    def callback(self, msg):
        _x().debug("Message %s %s", msg.routing_key, msg.body)
        if msg.body == self.QUIT_MESSAGE:
            self.do_ack(msg)
            msg.channel.basic_cancel(msg.consumer_tag)
            _x().debug("Q channel canceled")
            return
        try:
            if 'application/json' == msg.content_type:
                msg.body = json.loads(msg.body)
        except AttributeError:
            pass
        _ack, _reply = self.process_message(msg)
        if _reply:
            hdrs = _reply.application_headers
            next = hdrs.get('next', None)
            if next:
                exchange, routing_key = next.split('/')
                self.send(_reply, exchange, routing_key)
        if _ack:
            self.do_ack(msg)

    def send(self, msg, exchange, routing_key):
        try:
            if 'application/json' == msg.content_type:
                msg.body = json.dumps(msg.body)
        except AttributeError:
            pass
        # increment queue's message count
        k = self.queue_cache_key
        n = cache.get(k, 0)
        n += 1
        cache.set(k, n, _PENDING_QUEUE_TIMEOUT)
        self.channel.basic_publish(msg, exchange, routing_key=routing_key)

    @property
    def queue_cache_key(self):
        """Return the key where this queue's pending message count is cached"""
        return u"amqp:q:%s" % self.queue_name

    def get_pending_count(self):
        """Return the number of unprocessed messages in this queue"""
        return cache.get(self.queue_cache_key, 0)

    def call_fn(self, fn, msg, hdrs, next):
        # subclasses should override this if necessary
        return fn(msg, hdrs, next)

    def process_message(self, msg, retry_count=0):
        """Process this message and return tuple (do_ack, reply_msg).

        do_ack must be boolean.
        reply_msg, if not None, must have the property ``next`` in the format:
        exchange/routing_key

        """
        fn = None
        hdrs = None
        try:
            amqp_call_count = cache.get('amqp_call_count', 0)
            if amqp_call_count % 20 == 0:
                connection.close() # reset database connection after every 20 calls
                amqp_call_count = 0
                cache.close()
            cache.set('amqp_call_count', amqp_call_count+1, 300000)
        except Exception, e:
            _x().exception(e)
        try:
            _, _, fn = msg.routing_key.split('.')
            f = getattr(self, fn)
            hdrs = msg.application_headers
            try:
                next = msg.reply_to
            except AttributeError:
                next = None
            # decrement queue's message count
            k = self.queue_cache_key
            n = cache.get(k, 0)
            if n:
                n -= 1
                if n < 0:
                    n = 0
            cache.set(k, n, _PENDING_QUEUE_TIMEOUT)
            _reply = self.call_fn(f, msg, hdrs, next)
            return True, _reply
        except DatabaseError, de:
            _x().error("AMQP DB Error: %s, fn:%s, hdrs:%s, retry_count:%s", de, fn, hdrs, retry_count)
            _x().exception(de)
            try:
                transaction.rollback_unless_managed()
            except DatabaseError:
                pass
            connection.close()
            cache.close()
            if retry_count == 0:
                return self.process_message(msg, retry_count+1)
            return False, None
        except Exception, e:
            _x().error("AMQP Error msg: %s, fn:%s, hdrs:%s, retry_count:%s", e, fn, hdrs, retry_count)
            _x().exception(e)
            cache.close()
            return False, None

    def do_ack(self, msg):
        msg.channel.basic_ack(msg.delivery_tag)

    def listen(self):
        """Blocking listener"""
        if not self.blocking:
            raise Exception("Called listen() on a non-blocking queue")
        while self.channel.callbacks:
            self.channel.wait() # blocking call
        self.close()

    def do_pending(self, close=True):
        """Non-blocking message processing loop"""
        if self.blocking:
            raise Exception("Called do_pending() on a blocking queue")
        while True:
            msg = self.channel.basic_get(self.queue_name)
            if msg is None:
                break
            self.callback(msg)
        if close:
            self.close()

    def purge(self):
        cache.set(self.queue_cache_key, 0, _PENDING_QUEUE_TIMEOUT)
        n = self.channel.queue_purge(self.queue_name)
        _x().warn("Queue %s purged of %s messages", self.queue_name, n)

    def close(self):
        self.channel.close()
        if self.connection:
            self.connection.close()
        cache.close()
        _x().debug("Q listener stopped")

    def stop(self):
        from amqp import aq
        msg = aq.Message(self.QUIT_MESSAGE, delivery_mode=self.delivery_mode)
        self.channel.basic_publish(msg, self.exchange_name, routing_key=self.stop_routing_key)
        _x().debug("%s sent to %s/%s", msg.body, self.exchange_name, self.stop_routing_key)

