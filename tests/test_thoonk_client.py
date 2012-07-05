'''
Created on Jul 4, 2012

@author: iuri
'''
from twisted.trial import unittest
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet.endpoints import TCP4ClientEndpoint
from txthoonk.client import FeedExists, FeedDoesNotExist

REDIS_HOST = "localhost"
REDIS_PORT = 6381
REDIS_DB = 1

class Test(unittest.TestCase):


    @defer.inlineCallbacks
    def setUp(self):
        self.called = dict()

        from txthoonk.client import ThoonkFactory, Thoonk, ThoonkPubSub, \
            ThoonkPubSubFactory, Redis
        self.thoonk = Thoonk(Redis()) # pydev: force code completion
        self.pubsub = ThoonkPubSub(Redis()) # pydev: force code completion

        endpoint = TCP4ClientEndpoint(reactor, REDIS_HOST, REDIS_PORT)
        try:
            self.thoonk = yield endpoint.connect(ThoonkFactory(db=REDIS_DB))
            # flush redis database between calls
            self.thoonk.redis.flushdb()
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
        self.pubsub = yield endpoint.connect(ThoonkPubSubFactory())

        self._configure_wrappers()

    def tearDown(self):
        def closeRedis(*args):
            self.thoonk.redis.transport.loseConnection()
            self.pubsub.redis.transport.loseConnection()
            self.final_check()
        #d = defer.Deferred()
        #d.addCallback(closeRedis)
        #reactor.callLater(0.1, d.callback, 0) #@UndefinedVariable        
        #return d

        return reactor.callLater(0, closeRedis) #@UndefinedVariable

    def _configure_wrappers(self):
        msgRcvOrig = self.pubsub.redis.messageReceived
        self.msg_rcv = defer.Deferred()
        def msgRcvWrp(*args, **kwargs):
            msgRcvOrig(*args, **kwargs)
            self.msg_rcv.callback(None)
            self.msg_rcv = defer.Deferred()
        self.pubsub.redis.messageReceived = msgRcvWrp


    def check_called(self, func):
        """decorator to use in order to check if a callback was called"""
        self.called[func] = False
        def _check(*args, **kwargs):
            self.called[func] = True
            return func(*args, **kwargs)
        return _check

    def final_check(self):
        """Check if callbacks marked was called """
        for func in self.called.keys():
            self.assertTrue(self.called[func], "%s was not called" % (func,))

    ############################################################################
    #  Tests Redis Connection 
    ############################################################################

    @defer.inlineCallbacks
    def testPing(self):
        a = yield self.thoonk.redis.ping()
        self.assertEqual(a, 'PONG')

    ############################################################################
    #  Tests for create feed
    ############################################################################
    @defer.inlineCallbacks
    def testCreateFeed(self):
        feed_name = 'test_feed'

        yield self.thoonk.create_feed(feed_name)

        # check on redis
        ret = yield self.thoonk.redis.smembers("feeds")
        self.assertEqual(set([feed_name]), ret)

    @defer.inlineCallbacks
    def testHandlerCreateFeed(self):
        feed1 = 'feed1'

        @self.check_called
        def onCreate(ret_name):
            self.assertEqual(ret_name, feed1)

        yield self.pubsub.register_handler('create', onCreate)

        # Assuring that redis.messageReceived (pubsub was called)
        cb = self.msg_rcv
        yield self.thoonk.create_feed(feed1)
        yield cb

    @defer.inlineCallbacks
    def testHandlerCreateRemove(self):
        feed1 = 'feed1'
        feed2 = 'feed2'

        @self.check_called
        def onCreate(ret_name):
            self.assertEqual(ret_name, feed1)
        id_ = yield self.pubsub.register_handler('create', onCreate)

        # Assuring that redis.messageReceived (pubsub was called)
        cb = self.msg_rcv
        yield self.thoonk.create_feed(feed1)
        yield cb

        # check on redis
        ret = yield self.thoonk.redis.smembers("feeds")
        self.assertEqual(set([feed1]), ret)

        # same feed, must return a error

        self.assertFailure(self.thoonk.create_feed(feed1), FeedExists)

        # removing
        self.pubsub.remove_handler(id_)

        # Assuring that redis.messageReceived (pubsub was called)
        cb = self.msg_rcv
        yield self.thoonk.create_feed(feed2)
        yield cb

        # check on redis
        ret = yield self.thoonk.redis.smembers("feeds")
        self.assertEqual(set([feed2, feed1]), ret)

    @defer.inlineCallbacks
    def testFeedExists(self):
        feed_name = "test_feed"
        feed_exists = yield self.thoonk.feed_exists(feed_name)
        self.assertFalse(feed_exists);

        yield self.thoonk.create_feed(feed_name)
        feed_exists = yield self.thoonk.feed_exists(feed_name)
        self.assertTrue(feed_exists);

    ############################################################################
    #  Tests for config feed
    ############################################################################
    @defer.inlineCallbacks
    def testSetConfig(self):
        feed_name = "test_feed"
        config = {'blow': '2', 'blew': '1'}
        # set config on a non existing feed
        self.assertFailure(self.thoonk.set_config(feed_name, config), FeedDoesNotExist)

        yield self.thoonk.create_feed(feed_name)

        yield self.thoonk.set_config(feed_name, config)

        # check on redis
        ret = yield self.thoonk.redis.hgetall("feed.config:%s" % feed_name)

        self.assertEqual(ret, config)


if __name__ == "__main__":
    pass
