'''
Created on Jul 4, 2012

@author: iuri
'''
from twisted.trial import unittest
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet.endpoints import TCP4ClientEndpoint

REDIS_HOST = "localhost"
REDIS_PORT = 6381
REDIS_DB = 1

class TestThoonkBase(unittest.TestCase):
    timeout = 1

    @defer.inlineCallbacks
    def setUp(self):
        self.called = dict()

        from txthoonk.client import ThoonkPubFactory, ThoonkPub, ThoonkSub, \
            ThoonkSubFactory, Redis
        self.pub = ThoonkPub(Redis()) # pydev: force code completion
        self.sub = ThoonkSub(Redis()) # pydev: force code completion

        endpoint = TCP4ClientEndpoint(reactor, REDIS_HOST, REDIS_PORT)
        try:
            self.pub = yield endpoint.connect(ThoonkPubFactory(db=REDIS_DB))
            # flush redis database between calls
            self.pub.redis.flushdb()
        except:
            import os
            redis_conf = os.path.join(os.path.dirname(__file__), "redis.conf")
            msg = ("NOTE: Redis server not running on %s:%s. Please start \n"
                   "a local instance of Redis on this port to run unit tests \n"
                   "against.\n\n"
                   "You can use our supplied config:\n"
                   "  redis-server %s\n") % (REDIS_HOST, REDIS_PORT, redis_conf)
            raise unittest.SkipTest(msg)

        endpoint = TCP4ClientEndpoint(reactor, REDIS_HOST, REDIS_PORT)
        self.sub = yield endpoint.connect(ThoonkSubFactory())

        self._configure_wrappers()

    def tearDown(self):
        def closeRedis(*args):
            self.pub.redis.transport.loseConnection()
            self.sub.redis.transport.loseConnection()
            self.final_check()
        #d = defer.Deferred()
        #d.addCallback(closeRedis)
        #reactor.callLater(0.1, d.callback, 0) #@UndefinedVariable        
        #return d

        return reactor.callLater(0, closeRedis) #@UndefinedVariable

    def _configure_wrappers(self):
        msgRcvOrig = self.sub.redis.messageReceived
        self.msg_rcv = defer.Deferred()
        def msgRcvWrp(*args, **kwargs):
            """
            Configure a callback to be executed in each message received by
            RedisSubscriber
            """
            msgRcvOrig(*args, **kwargs)
            self.msg_rcv.callback(None)
            self.msg_rcv = defer.Deferred()
        self.sub.redis.messageReceived = msgRcvWrp

    def check_called(self, func):
        """decorator to use in order to check if a callback was called"""
        self.called[func] = False
        def _check(*args, **kwargs):
            self.called[func] = True
            return func(*args, **kwargs)
        return _check

    def final_check(self):
        """Check if callbacks marked were called"""
        for func in self.called.keys():
            self.assertTrue(self.called[func], "%s was not called" % (func,))


class TestThoonkPubSub(TestThoonkBase):
    ############################################################################
    #  Tests Redis Connection 
    ############################################################################

    @defer.inlineCallbacks
    def testPing(self):
        a = yield self.pub.redis.ping()
        self.assertEqual(a, 'PONG')

    ############################################################################
    #  Tests for create feed
    ############################################################################
    @defer.inlineCallbacks
    def testCreateFeed(self):
        feed_name = 'test_feed'

        yield self.pub.create_feed(feed_name)

        # check on redis
        ret = yield self.pub.redis.smembers("feeds")
        self.assertEqual(set([feed_name]), ret)

    @defer.inlineCallbacks
    def testHandlerCreateFeed(self):
        feed1 = 'feed1'

        @self.check_called
        def onCreate(ret_name, *args):
            self.assertEqual(ret_name, feed1)

        yield self.sub.register_handler('create', onCreate)

        # Assuring that redis.messageReceived (sub was called)
        cb = self.msg_rcv
        yield self.pub.create_feed(feed1)
        yield cb

    @defer.inlineCallbacks
    def testHandlerCreateRegisterRemove(self):
        feed1 = 'feed1'
        feed2 = 'feed2'

        @self.check_called
        def onCreate(ret_name, *args):
            self.assertEqual(ret_name, feed1)
        id_ = yield self.sub.register_handler('create', onCreate)

        # Assuring that redis.messageReceived (sub) was called
        cb = self.msg_rcv
        yield self.pub.create_feed(feed1)
        yield cb

        # check on redis
        ret = yield self.pub.redis.smembers("feeds")
        self.assertEqual(set([feed1]), ret)

        # same feed, must return a error
        from txthoonk.client import FeedExists
        self.assertFailure(self.pub.create_feed(feed1), FeedExists)

        # removing
        self.sub.remove_handler(id_)

        # Assuring that redis.messageReceived (sub) was called
        cb = self.msg_rcv
        yield self.pub.create_feed(feed2)
        yield cb

        # check on redis
        ret = yield self.pub.redis.smembers("feeds")
        self.assertEqual(set([feed2, feed1]), ret)

    @defer.inlineCallbacks
    def testFeedExists(self):
        feed_name = "test_feed"
        feed_exists = yield self.pub.feed_exists(feed_name)
        self.assertFalse(feed_exists);

        yield self.pub.create_feed(feed_name)
        feed_exists = yield self.pub.feed_exists(feed_name)
        self.assertTrue(feed_exists);

    @defer.inlineCallbacks
    def testFeedNames(self):
        # no feeds
        ret = yield self.pub.get_feed_names()
        self.assertEqual(set(), ret)

        # create some feeds
        feeds = set(["feed1", "feed2", "feed3"])
        for feed in feeds:
            yield self.pub.create_feed(feed)

        ret = yield self.pub.get_feed_names()
        self.assertEqual(feeds, ret)

    ############################################################################
    #  Tests for config feed
    ############################################################################
    @defer.inlineCallbacks
    def testSetConfig(self):
        feed_name = "test_feed"
        config = {'blow': '2', 'blew': '1'}

        # set config on a non existing feed
        from txthoonk.client import FeedDoesNotExist
        self.assertFailure(self.pub.set_config(feed_name, config),
                           FeedDoesNotExist)

        yield self.pub.create_feed(feed_name)

        yield self.pub.set_config(feed_name, config)

        # check on redis
        ret = yield self.pub.redis.hgetall("feed.config:%s" % feed_name)

        self.assertEqual(ret, config)

    @defer.inlineCallbacks
    def testGetConfig(self):
        feed_name = "test_feed"
        config = {'blow': '2', 'blew': '1'}

        yield self.pub.create_feed(feed_name)
        yield self.pub.set_config(feed_name, config)

        # get the config
        ret = yield self.pub.get_config(feed_name)
        self.assertEqual(ret, config)

    ############################################################################
    #  Tests for delete feed
    ############################################################################
    @defer.inlineCallbacks
    def testDeleteFeed(self):
        feed_name = "test_feed"
        config = {'name': 'feed', 'surname': 'blow'}

        # delete a non-existing feed
        from txthoonk.client import FeedDoesNotExist
        self.assertFailure(self.pub.delete_feed("teste"), FeedDoesNotExist)

        yield self.pub.create_feed(feed_name, config)
        feed_exists = yield self.pub.feed_exists(feed_name)
        self.assertTrue(feed_exists);

        ret = yield self.pub.delete_feed(feed_name)
        self.assertTrue(ret)

        feed_exists = yield self.pub.feed_exists(feed_name)
        self.assertFalse(feed_exists);

        # check config has on redis
        ret = yield self.pub.redis.hgetall("feed.config:%s" % feed_name)
        self.assertEqual(ret, {})

    @defer.inlineCallbacks
    def testHandlerDeleteFeed(self):
        feed1 = 'feed1'

        @self.check_called
        def onDelete(ret_name, *args):
            self.assertEqual(ret_name, feed1)

        yield self.sub.register_handler('delete', onDelete)

        yield self.pub.create_feed(feed1)
        # Assuring that redis.messageReceived (sub) was called
        cb = self.msg_rcv
        yield self.pub.delete_feed(feed1)
        yield cb

    ############################################################################
    #  Tests for feed types
    ############################################################################
    @defer.inlineCallbacks
    def testTypeFeed(self):
        feed_name = "test"
        feed = yield self.pub.feed(feed_name)
        from txthoonk.types import Feed
        self.assertIsInstance(feed, Feed)

        feed_exists = yield self.pub.feed_exists(feed_name)
        self.assertTrue(feed_exists)


    ############################################################################
    #  Tests for publish_channel
    ############################################################################
    @defer.inlineCallbacks
    def testPublishChannel(self):
        args = ('a', 'b', 'abc', '', '1')
        channel = 'mychannel'
        @self.check_called
        def onMyChannel(*ret_args):
            self.assertEquals(args, ret_args)

        yield self.sub.register_handler(channel, onMyChannel)

        # Assuring that redis.messageReceived (sub) was called
        cb = self.msg_rcv
        yield self.pub.publish_channel(channel, *args)
        yield cb

if __name__ == "__main__":
    pass
