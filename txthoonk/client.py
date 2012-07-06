from zope.interface import implements #@UnresolvedImport

from twisted.internet.protocol import ReconnectingClientFactory

from txredis.protocol import Redis, RedisSubscriber, defer
from twisted.internet import interfaces

import uuid
import itertools

class FeedExists(Exception):
    pass

class FeedDoesNotExist(Exception):
    pass

class Empty(Exception):
    pass

class NotListening(Exception):
    pass


class ThoonkBase(object):
    SEPARATOR = "\x00"
    implements(interfaces.IProtocol)

    def __init__(self, redis):
        self.set_redis(redis)
        self._uuid = uuid.uuid4().hex

    def set_redis(self, redis):
        self.redis = redis

    def dataReceived(self, data):
        """
        Called whenever data is received.

        Use this method to translate to a higher-level message.  Usually, some
        callback will be made upon the receipt of each complete protocol
        message.

        @param data: a string of indeterminate length.  Please keep in mind
            that you will probably need to buffer some data, as partial
            (or multiple) protocol messages may be received!  I recommend
            that unit tests for protocols call through to this method with
            differing chunk sizes, down to one byte at a time.
        """
        self.redis.dataReceived(data)

    def connectionLost(self, reason):
        """
        Called when the connection is shut down.

        Clear any circular references here, and any external references
        to this Protocol.  The connection has been closed. The C{reason}
        Failure wraps a L{twisted.internet.error.ConnectionDone} or
        L{twisted.internet.error.ConnectionLost} instance (or a subclass
        of one of those).

        @type reason: L{twisted.python.failure.Failure}
        """
        self.redis.connectionLost(reason)

    def makeConnection(self, transport):
        """
        Make a connection to a transport and a server.
        """
        self.redis.makeConnection(transport)

    def connectionMade(self):
        """
        Called when a connection is made.

        This may be considered the initializer of the protocol, because
        it is called when the connection is completed.  For clients,
        this is called once the connection to the server has been
        established; for servers, this is called after an accept() call
        stops blocking and a socket has been received.  If you need to
        send any greeting or initial message, do it here.
        """
        self.redis.connectionMade()

class ThoonkPub(ThoonkBase):
    redis = Redis() # pydev: force code completion

    def create_feed(self, feed_name, config={}):
        """
        Create a new feed with a given configuration.
        
        The configuration is a dict, and should include a 'type'
        entry with the class of the feed type implementation.
        
        Arguments:
            feed -- The name of the new feed.
            config -- A dictionary of configuration values.
        """
        def _set_config(ret):
            return self.set_config(feed_name, config)

        def _publish(ret):
            if ret == 1:
                d = self.redis.publish("newfeed", self.SEPARATOR.join([feed_name, self._uuid]))
                d.addCallback(_set_config)
                return d
            else:
                d = defer.Deferred()
                d.errback(FeedExists())
                return d

        return self.redis.sadd("feeds", feed_name).addCallback(_publish)

    def feed_exists(self, feed_name):
        """
        Check if a given feed exists.

        Arguments:
            feed -- The name of the feed.
        """

        return self.redis.sismember("feeds", feed_name)

    def set_config(self, feed_name, config):
        """
        Set the configuration for a given feed.
        
        Arguments:
            feed -- The name of the feed.
            config -- A dictionary of configuration values.
        """
        def _exists(ret):
            if not ret:
                d = defer.Deferred()
                d.errback(FeedDoesNotExist())
                return d

            dl = []
            for k, v in config.items():
                dl.append(self.redis.hset('feed.config:%s' % feed_name, k, v))
            return defer.DeferredList(dl)
        return self.feed_exists(feed_name).addCallback(_exists)

    def get_feed_names(self):
        """
        Return the set of known feeds.

        Returns: a defer with the set result as first argument
        """
        return self.redis.smembers("feeds")

class ThoonkPubFactory(ReconnectingClientFactory):
    protocol = Redis
    protocol_wrapper = ThoonkPub

    def __init__(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs

    def buildProtocol(self, addr):
        """
        Called when a connection has been established to addr.

        If None is returned, the connection is assumed to have been refused,
        and the Port will close the connection.

        @type addr: (host, port)
        @param addr: The address of the newly-established connection

        @return: None if the connection was refused, otherwise an object
                 providing L{IProtocol}.
        """

        redis = self.protocol(*self._args, **self._kwargs)
        self.resetDelay()
        return self.protocol_wrapper(redis)

class ThoonkSub(ThoonkBase):
    redis = RedisSubscriber() # pydev: force code completion

    def __init__(self, redis):
        self._handlers = {'id_gen': itertools.count(), #@UndefinedVariable
                          'evt_handlers': {'create': dict()},
                          'id2evt' : {}}

        self._channels_maps = {"newfeed": "create"}
        # delay subscribe 
        self._subscribed = {'running': False,
                            'subscribed': {},
                            'running_for': None,
                            'defer': None}

        super(ThoonkSub, self).__init__(redis)

    def set_redis(self, redis):
        redis.messageReceived = self.messageReceived
        redis.channelSubscribed = self.channelSubscribed
        super(ThoonkSub, self).set_redis(redis)

    def _get_sub_channel_cb(self, channel):
        return lambda arg: self._sub_channel(channel)

    def _sub_channel(self, channel):
        """
        Subscribe to a channel using a defer
        """
        if self._subscribed['subscribed'].get(channel):
            # already subcribed
            d = defer.Deferred()
            d.callback(True)
            return d

        if self._subscribed['running']:
            # call it later, queue it
            d = self._subscribed['defer']
            d.addCallback(self._get_sub_channel_cb(channel))
            return d

        def set_subscribed(*args):
            self._subscribed['running'] = False
            self._subscribed['subscribed'][channel] = True
            return True

        self._subscribed['running'] = True
        self.redis.subscribe(channel)

        d = defer.Deferred()
        self._subscribed['defer'] = d
        self._subscribed['running_for'] = channel

        return d.addCallback(set_subscribed)

    def register_handler(self, evt, handler):
        """
        Register a function to respond to feed events.
        
        Event types:
            - create
        
        Arguments:
            evt -- The name of the feed event.
            handler -- The function for handling the event.
        """
        def register_callback(*args):
            id_ = self._handlers['id_gen'].next()

            # store map id -> evt
            self._handlers['id2evt'][id_] = evt

            # store handler on evt
            self._handlers['evt_handlers'][evt][id_] = handler
            return id_

        if evt not in self._handlers['evt_handlers'].keys():
            d = defer.Deferred()
            d.callback(None)

        return self._sub_channel('newfeed').addCallback(register_callback)

    def remove_handler(self, id_):
        """
        Unregister a function that was registered via register_handler

        Arguments:
            id_ - the handler id
        """

        evt = self._handlers['id2evt'].get(id_)
        if not evt:
            return

        del self._handlers['evt_handlers'][evt][id_]
        del self._handlers['id2evt'][id_]

    def messageReceived(self, channel, message):
        """
        Called when this connection is subscribed to a channel that
        has received a message published on it.
        """
        evt = self._channels_maps.get(channel)
        if evt is None:
            return

        if not self.SEPARATOR in message:
            return

        for handler in self._handlers['evt_handlers'][evt].values():
            handler(message.split(self.SEPARATOR)[0])

    def channelSubscribed(self, channel, numSubscriptions):
        """
        Called when a channel is subscribed to.
        """
        assert self._subscribed['running']
        assert self._subscribed['running_for'] == channel
        d = self._subscribed['defer']
        d.callback(True)

class ThoonkSubFactory(ThoonkPubFactory):
    protocol = RedisSubscriber
    protocol_wrapper = ThoonkSub

