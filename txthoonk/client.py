from zope.interface import implements #@UnresolvedImport

from twisted.internet.protocol import ReconnectingClientFactory

from txredis.protocol import Redis, RedisSubscriber, defer
from twisted.internet import interfaces

import uuid
import itertools
from txthoonk.types import Feed

try:
    from collection import OrderedDict
except ImportError:
    OrderedDict = dict

class FeedExists(Exception):
    pass

class FeedDoesNotExist(Exception):
    pass


class ThoonkBase(object):
    """
    Thoonk object base class.
    """
    SEPARATOR = "\x00"
    implements(interfaces.IProtocol)

    def __init__(self, redis):
        '''
        Constructor

        @param redis: the txredis instance
        '''
        self.set_redis(redis)
        self._uuid = uuid.uuid4().hex

    def set_redis(self, redis):
        '''
        Set the txredis instance

        @param redis: the txredis instance
        '''
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
    '''
    Thoonk publisher class
    '''
    redis = Redis() # pydev: force code completion

    def __init__(self, *args, **kwargs):
        self.feed = self._get_feed_type(Feed, type_="feed")
        super(ThoonkPub, self).__init__(*args, **kwargs)

    def _get_feed_type(self, kls, type_):
        '''
        Returns a function in order to generate a specific feed type

        @param kls: the python class of feed
        @param type_: the type of feed to be stored in.
        '''
        config = {'type': type_}
        def _create_type(feed_name):
            '''
            Creates a new feed of this type.

            @param feed_name: the name of the feed.
            '''
            def _get_feed(*args):
                """Create a new a new instance of passed class"""
                return kls(pub=self, name=feed_name)
            def _exists(ret):
                """
                Called when self.feed_exists returns
                """
                if ret:
                    return _get_feed()

                d = self.create_feed(feed_name, config)
                d.addCallback(_get_feed)
                return d

            return self.feed_exists(feed_name).addCallback(_exists)

        return _create_type

    def _publish_channel(self, channel, *args):
        """Calls self.publish_channel appending self._uuid at end"""
        args = list(args) + [self._uuid]
        return self.publish_channel(channel, *args)

    def publish_channel(self, channel, *args):
        '''
        Publish on channel.

        @param channel: the channel where message will be published
        @param *args: a list that will compose the message
        '''
        message = self.SEPARATOR.join(args)
        return self.redis.publish(channel, message)

    def create_feed(self, feed_name, config={}):
        """
        Create a new feed with a given configuration.

        The configuration is a dict, and should include a 'type'
        entry with the class of the feed type implementation.

        @param feed_name: The name of the new feed.
        @param config: A dictionary of configuration values.
        """
        def _set_config(ret):
            '''
            Called when self._publish_channel returns.
            '''
            return self.set_config(feed_name, config)

        def _publish(ret):
            """
            Called when redis.sadd returns.
            """
            if ret == 1:
                d = self._publish_channel("newfeed", feed_name)
                d.addCallback(_set_config)
                return d
            else:
                return defer.fail(FeedExists())

        return self.redis.sadd("feeds", feed_name).addCallback(_publish)

    def delete_feed(self, feed_name):
        """
        Delete a given feed.

        @param feed_name: The name of the feed.
        """
        hash_feed_config = "feed.config:%s" % feed_name

        def _exec_check(bulk_result):
            # All defers must be succeed
            assert all([a[0] for a in bulk_result])
            # assert number of commands
            assert len(bulk_result) == 7

            multi_result = bulk_result[-1][1]
            if multi_result:
                # transaction done :D
                # assert number commands in transaction
                assert len(multi_result) == 3
                # check if feed_name existed when was deleted
                exists = multi_result[0]
                if not exists:
                    return defer.fail(FeedDoesNotExist())
                return True

            # transaction fail :-(
            # repeat it
            return self.delete_feed(feed_name)

        defers = []
        # issue all commands in order to avoid concurrent calls
        defers.append(self.redis.watch("feeds")) #0
        defers.append(self.redis.watch(hash_feed_config)) #1
        # begin transaction
        defers.append(self.redis.multi()) #2
        defers.append(self.redis.srem("feeds", feed_name)) #3 - #0
        defers.append(self.redis.delete(hash_feed_config)) #4 - #1
        defers.append(self._publish_channel("delfeed", feed_name)) #5 - #2
        # end transaction
        defers.append(self.redis.execute()) #6

        return defer.DeferredList(defers).addCallback(_exec_check)

    def feed_exists(self, feed_name):
        """
        Check if a given feed exists.

        @param feed_name: The name of the feed.
        """

        return self.redis.sismember("feeds", feed_name)

    def set_config(self, feed_name, config):
        """
        Set the configuration for a given feed.

        @param feed_name: The name of the feed.
        @param config: A dictionary of configuration values.
        """
        def _exists(ret):
            if not ret:
                return defer.fail(FeedDoesNotExist())

            dl = []
            for k, v in config.items():
                dl.append(self.redis.hset('feed.config:%s' % feed_name, k, v))
            return defer.DeferredList(dl)

        return self.feed_exists(feed_name).addCallback(_exists)

    def get_config(self, feed_name):
        """
        Get the configuration for a given feed.

        @param feed_name: The name of the feed.

        @return: A defer witch callback function will have a config dict
                 as the first argument
        """
        def _exists(ret):
            if not ret:
                return defer.fail(FeedDoesNotExist())

            return self.redis.hgetall('feed.config:%s' % feed_name)

        return self.feed_exists(feed_name).addCallback(_exists)

    def get_feed_names(self):
        """
        Return the set of known feeds.

        @return: a defer witch callback function will have the set result
                as first argument
        """
        return self.redis.smembers("feeds")

class ThoonkPubFactory(ReconnectingClientFactory):
    '''
    ThoonkPub Factory
    '''
    protocol = Redis
    protocol_wrapper = ThoonkPub

    def __init__(self, *args, **kwargs):
        '''
        Constructor
        '''
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
    '''
    Thoonk Subscriber class.
    '''
    redis = RedisSubscriber() # pydev: force code completion

    def __init__(self, redis):
        '''
        Constructor

        @param redis: the txredis instance
        '''
        self._handlers = {'id_gen': itertools.count(), #@UndefinedVariable
                          'channel_handlers': {},
                          'id2channel' : {}}
        # delay subscribe
        self._subscribed = {'running': False,
                            'subscribed': {},
                            'running_for': None,
                            'defer': None}

        super(ThoonkSub, self).__init__(redis)

    def _get_sub_channel_cb(self, channel):
        '''
        Returns a callback in order to subscribe one channel.

        @param channel: the desired channel.
        '''
        return lambda arg: self._sub_channel(channel)

    def _evt2channel(self, evt):
        '''
        Convert Thoonk.py channels in compatible events

        @param evt: the event
        '''
        # Thoonk.py compatible events
        channel = evt
        if evt == "create":
            channel = "newfeed"
        elif evt == "delete":
            channel = "delfeed"
        return channel

    def _sub_channel(self, channel):
        """
        Subscribe to a channel using a defer.

        This call will queue channel subscriptions.

        @param channel: the desired channel.
        """
        if self._subscribed['subscribed'].get(channel):
            # already subcribed
            return defer.succeed(True)

        if self._subscribed['running']:
            # call it later, queue it
            d = self._subscribed['defer']
            d.addCallback(self._get_sub_channel_cb(channel))
            return d

        def set_subscribed(*args):
            '''
            Called when channel was subscribed.
            '''
            self._subscribed['running'] = False
            self._subscribed['subscribed'][channel] = True
            return True

        self._subscribed['running'] = True
        self.redis.subscribe(channel)

        d = defer.Deferred()
        self._subscribed['defer'] = d
        self._subscribed['running_for'] = channel

        return d.addCallback(set_subscribed)

    def set_redis(self, redis):
        '''
        Set the txredis instance

        @param redis: the txredis instance
        '''
        # FIXME: on (re)connect (re)subscribe all channels
        redis.messageReceived = self.messageReceived
        redis.channelSubscribed = self.channelSubscribed
        super(ThoonkSub, self).set_redis(redis)

    def register_handler(self, evt, handler):
        """
        Register a function to respond to feed events.

        Event types/handler params:
        - create                 handler(feedname)
        - newfeed                handler(feedname)
        - delete                 handler(feedname)
        - delfeed                handler(feedname)
        - feed.publish:[feed]    handler(id, item)
        - feed.retract:[feed]    handler(id)
        - feed.edit:[feed]       handler(id, item)

        @param evt: The name of the feed event.
        @param handler: The function for handling the event.
        """
        channel = self._evt2channel(evt)

        if not channel:
            return defer.succeed(None)

        def _register_callback(*args):
            """
            Called when channel was subscribed.
            """
            id_ = self._handlers['id_gen'].next()

            # store map id -> channel
            self._handlers['id2channel'][id_] = channel

            handlers = self._handlers['channel_handlers'].get(channel)
            if not handlers:
                handlers = self._handlers['channel_handlers'][channel] = OrderedDict()

            # store handler
            handlers[id_] = handler
            return id_

        return self._sub_channel(channel).addCallback(_register_callback)

    def remove_handler(self, id_):
        """
        Unregister a function that was registered via register_handler

        @param id_: the handler id
        """

        channel = self._handlers['id2channel'].get(id_)
        if not channel:
            return

        del self._handlers['channel_handlers'][channel][id_]
        del self._handlers['id2channel'][id_]

    def messageReceived(self, channel, message):
        """
        Called when this connection is subscribed to a channel that
        has received a message published on it.
        """
        handlers = self._handlers['channel_handlers'].get(channel)
        if handlers is None:
            return

        for handler in handlers.values():
            args = message.split(self.SEPARATOR)
            handler(*args)

    def channelSubscribed(self, channel, numSubscriptions):
        """
        Called when a channel is subscribed to.
        """
        assert self._subscribed['running']
        assert self._subscribed['running_for'] == channel
        d = self._subscribed['defer']
        d.callback(True)

class ThoonkSubFactory(ThoonkPubFactory):
    '''
    ThoonkSub Factory class.
    '''
    protocol = RedisSubscriber
    protocol_wrapper = ThoonkSub

