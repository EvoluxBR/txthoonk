'''
Created on Jul 4, 2012

@author: iuri
'''
from twisted.trial import unittest
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet.endpoints import TCP4ClientEndpoint

REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 15

class Test(unittest.TestCase):

    def setUp(self):
        from txthoonk.client import ThoonkFactory
        def got_proto(thoonk):
            self.thoonk = thoonk
            self.redis = thoonk.redis

        def err_connect(res):
            msg = ("NOTE: Redis server not running on %s:%s. Please start \n"
                    "a local instance of Redis on this port to run unit tests \n"
                    "against.") % (REDIS_HOST, REDIS_PORT)
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
        a = yield self.thoonk.redis.ping()
        self.assertEqual(a, 'PONG')


if __name__ == "__main__":
    pass
