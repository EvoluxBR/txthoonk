'''
Created on Jul 9, 2012

@author: iuri
'''
import sys

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet import reactor
from twisted.internet.endpoints import TCP4ClientEndpoint

from txthoonk.client import ThoonkPubFactory, ThoonkSubFactory
from twisted.python import log

REDIS_HOST, REDIS_PORT = ("localhost", 6379)


@inlineCallbacks
def getThoonkSubscriber():
    endpoint = TCP4ClientEndpoint(reactor, REDIS_HOST, REDIS_PORT)
    sub = yield endpoint.connect(ThoonkSubFactory())
    returnValue(sub)

@inlineCallbacks
def getThoonkPublisher(db=15):
    endpoint = TCP4ClientEndpoint(reactor, REDIS_HOST, REDIS_PORT)
    pub = yield endpoint.connect(ThoonkPubFactory(db=db))
    returnValue(pub)


def newfeed(*args):
    log.msg("newfeed: %r" % [args])

def delfeed(*args):
    log.msg("delfeed: %r" % [args])

def publish(*args):
    log.msg("publish: %r" % [args])

def retract(*args):
    log.msg("retract: %r" % [args])

def edit(*args):
    log.msg("edit: %r" % [args])

@inlineCallbacks
def runTest01():
    pub = yield getThoonkPublisher()
    sub = yield getThoonkSubscriber()

    feed_name = "test"
    #flush redis
    yield pub.redis.flushdb

    # setup handlers
    id_ = yield sub.register_handler("newfeed", newfeed)
    log.msg("handler for newfeed id: %r" % id_)

    id_ = yield sub.register_handler("delfeed", delfeed)
    log.msg("handler for delfeed id: %r" % id_)


    feed = yield pub.feed(feed_name)
    for chan, handler in zip([feed.channel_publish,
                              feed.channel_edit,
                              feed.channel_retract],
                             [publish,
                              edit,
                              retract]):
        id_ = yield sub.register_handler(chan, handler)
        log.msg("handler for %r id: %r" % (chan, id_))

    # publish without id 
    new_item_id = yield feed.publish("new item")

    # publish with id
    another_item_id = "someid"
    yield feed.publish("another item", another_item_id)

    # publish with same id
    yield feed.publish("replace item", another_item_id)

    # retract ids
    yield feed.retract(new_item_id)
    yield feed.retract(another_item_id)

    yield pub.delete_feed(feed_name)


@inlineCallbacks
def runTest02():
    pub = yield getThoonkPublisher(12)
    #sub = yield getThoonkSubscriber()

    feed_name = "test2"
    yield pub.redis.flushdb()

    feed = yield pub.feed(feed_name)

    # set config
    yield feed.set_config({"max_length": 1})

    @inlineCallbacks
    def publish(array):
        for a in array:
            log.msg("publishing: %r" % a)
            yield feed.publish(a)
            log.msg("published:  %r" % a)

    @inlineCallbacks
    def get_items():
        ids = yield feed.get_ids()
        for id_ in ids:
            item = yield feed.get_id(id_)
            log.msg("got item: %r" % item)

    import string
    reactor.callLater(0, publish, string.ascii_lowercase)
    reactor.callLater(0, publish, string.ascii_uppercase)
    reactor.callLater(0.5, get_items)

def main(*args):
    log.startLogging(sys.stdout)
    reactor.callLater(0, runTest01) #@UndefinedVariable
    reactor.callLater(0.5, runTest02) #@UndefinedVariable
    reactor.callLater(1.5, reactor.stop) #@UndefinedVariable

    reactor.run() #@UndefinedVariable

if __name__ == '__main__':
    main(sys.argv)
