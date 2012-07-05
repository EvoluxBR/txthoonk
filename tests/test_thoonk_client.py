'''
Created on Jul 4, 2012

@author: iuri
'''
from twisted.trial import unittest
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet.endpoints import TCP4ClientEndpoint
from txthoonk.client import FeedExists

REDIS_HOST = "localhost"
REDIS_PORT = 6381
REDIS_DB = 1

class Test(unittest.TestCase):

    def check_called(self, func):
        self.called[func] = False
        def _check(*args, **kwargs):
            self.called[func] = True
            return func(*args, **kwargs)
        return _check

    def final_check(self):
        for func in self.called.keys():
            self.assertTrue(self.called[func], "%s was not called" % (func,))

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

    def _configure_wrappers(self):
        msgRcvOrig = self.pubsub.redis.messageReceived
        self.msg_rcv = defer.Deferred()
        def msgRcvWrp(*args, **kwargs):
            msgRcvOrig(*args, **kwargs)
            self.msg_rcv.callback(None)
            self.msg_rcv = defer.Deferred()
        self.pubsub.redis.messageReceived = msgRcvWrp

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

    @defer.inlineCallbacks
    def testPing(self):
        a = yield self.thoonk.redis.ping()
        self.assertEqual(a, 'PONG')

    @defer.inlineCallbacks
    def testCreateFeed(self):
        feed_name = 'test_feed'

        yield self.thoonk.create_feed(feed_name)
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

        ret = yield self.thoonk.redis.smembers("feeds")
        self.assertEqual(set([feed2, feed1]), ret)


if __name__ == "__main__":
    pass
