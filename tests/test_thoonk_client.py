'''
Created on Jul 4, 2012

@author: iuri
'''
from twisted.trial import unittest
from twisted.internet import defer, protocol
from twisted.internet import reactor

REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 15

class Test(unittest.TestCase):

    def setUp(self):
        from txthoonk.client import ThoonkFactory
        def got_proto(redis):
            self.thoonk = ThoonkFactory.protocol_wrapper(redis)
            self.redis = redis

        def err_connect(res):
            msg = ("NOTE: Redis server not running on %s:%s. Please start \n"
                    "a local instance of Redis on this port to run unit tests \n"
                    "against.") % (REDIS_HOST, REDIS_PORT)
            raise unittest.SkipTest(msg)

        clientCreator = protocol.ClientCreator(reactor, ThoonkFactory.protocol)
        d = clientCreator.connectTCP(REDIS_HOST, REDIS_PORT)

        d.addCallback(got_proto)
        d.addErrback(err_connect)

        return d

    def tearDown(self):
        self.redis.transport.loseConnection()

    @defer.inlineCallbacks
    def testName(self):
        #self.assertEqual(True, True)
        yield


if __name__ == "__main__":
    pass
