from zope.interface import implements #@UnresolvedImport

from twisted.internet.protocol import ReconnectingClientFactory

from txredis.protocol import Redis, RedisSubscriber, defer
from twisted.internet import interfaces

import uuid
import itertools
from twisted.python import failure


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
        self.redis = redis
        self._uuid = uuid.uuid4().hex

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

class Thoonk(ThoonkBase):
    redis = Redis() # pydev: force code completion

    def create_feed(self, feed_name):
        def _publish(ret):
            if ret == 1:
                return self.redis.publish("newfeed", self.SEPARATOR.join([feed_name, self._uuid]))
            else:
                d = defer.Deferred()
                d.errback(FeedExists())
                return d

        return self.redis.sadd("feeds", feed_name).addCallback(_publish)

class ThoonkFactory(ReconnectingClientFactory):
    protocol = Redis
    protocol_wrapper = Thoonk

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

class ThoonkPubSub(ThoonkBase):
    redis = RedisSubscriber() # pydev: force code completion
    def __init__(self, redis):
        redis.messageReceived = self.messageReceived
        redis.channelSubscribed = self.channelSubscribed

        self._handlers = {'id_gen': itertools.count(), #@UndefinedVariable
                          'evt_handlers': {'create': dict()},
                          'id2evt' : {}}

        self._channels_maps = {"newfeed": "create", "onrock": None}
        # delay subscribe 
        self._subscribed = {'running': False,
                            'subscribed': False,
                            'defers': {},
                            'dl': None}

        super(ThoonkPubSub, self).__init__(redis)

    def _subscribe(self):
        if self._subscribed['subscribed']:
            return defer.Deferred.callback(None)

        if self._subscribed['running']:
            return self._subscribed['dl']

        self._subscribed['running'] = True
        def set_subscribed(*args):
            self._subscribed['running'] = False
            self._subscribed['subscribed'] = True
            return None

        for channel in self._channels_maps.keys():
            self.redis.subscribe(channel)
            d = defer.Deferred()
            self._subscribed['defers'][channel] = d

        dl = defer.DeferredList(self._subscribed['defers'].values())

        return dl.addCallback(set_subscribed)

    def register_handler(self, evt, handler):
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

        return self._subscribe().addCallback(register_callback)


    def remove_handler(self, id_):
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
        d = self._subscribed['defers'][channel]
        d.callback(None)

class ThoonkPubSubFactory(ThoonkFactory):
    protocol = RedisSubscriber
    protocol_wrapper = ThoonkPubSub

