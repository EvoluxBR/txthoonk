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

class Test(unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        from txthoonk.client import ThoonkFactory, Thoonk, ThoonkPubSub, \
            ThoonkPubSubFactory
        self.thoonk = Thoonk(None) # pydev: force code completion
        self.pubsub = ThoonkPubSub(None) # pydev: force code completion

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
        self.pubsub = yield endpoint.connect(ThoonkPubSubFactory(db=REDIS_DB))


    def tearDown(self):
        def closeRedis():
            self.thoonk.redis.transport.loseConnection()
            self.pubsub.redis.transport.loseConnection()
        reactor.callLater(0, closeRedis) #@UndefinedVariable

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


if __name__ == "__main__":
    pass
