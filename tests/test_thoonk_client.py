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

    def setUp(self):
        from txthoonk.client import ThoonkFactory, Thoonk, Redis
        self.redis = Redis() # pydev: force code completion
        self.thoonk = Thoonk(None) # pydev: force code completion

        def got_proto(thoonk):
            self.thoonk = thoonk
            self.redis = thoonk.redis
            # flush
            self.redis.flushdb()

        def err_connect(res):
            import os
            redis_conf = os.path.join(os.path.dirname(__file__), "redis.conf")
            msg = ("NOTE: Redis server not running on %s:%s. Please start \n"
                    "a local instance of Redis on this port to run unit tests \n"
                    "against.\n\n"
                    "You can use our supplied config:\n"
                    "  redis-server %s\n") % (REDIS_HOST, REDIS_PORT, redis_conf)
            raise unittest.SkipTest(msg)

        endpoint = TCP4ClientEndpoint(reactor, REDIS_HOST, REDIS_PORT)
        d = endpoint.connect(ThoonkFactory(db=REDIS_DB))

        d.addCallback(got_proto)
        d.addErrback(err_connect)

        return d

    def tearDown(self):
        self.redis.transport.loseConnection()

    @defer.inlineCallbacks
    def testPing(self):
        a = yield self.redis.ping()
        self.assertEqual(a, 'PONG')


if __name__ == "__main__":
    pass
