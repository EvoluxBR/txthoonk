'''
Created on Jul 6, 2012

@author: iuri
'''
from tests.test_thoonk_pubsub import TestThoonkBase
from twisted.internet import defer

class TestThoonkFeed(TestThoonkBase):
    @defer.inlineCallbacks
    def setUp(self):
        yield TestThoonkBase.setUp(self)

        self.feed_name = "teste"
        self.config = {'type': 'feed'}
        yield self.pub.create_feed(self.feed_name, self.config)

        from txthoonk.types import Feed
        self.feed = Feed(pub=self.pub, name=self.feed_name)

        # check properties
        self.assertEqual(self.pub, self.feed.pub)
        self.assertEqual(self.feed_name, self.feed.name)

        self.assertEqual(self.feed.feed_ids,
                         "feed.ids:%s" % self.feed_name)
        self.assertEqual(self.feed.feed_items,
                         "feed.items:%s" % self.feed_name)
        self.assertEqual(self.feed.feed_publishes,
                         "feed.publishes:%s" % self.feed_name)
        self.assertEqual(self.feed.feed_config,
                         "feed.config:%s" % self.feed_name)

        self.assertEqual(self.feed.channel_retract,
                         "feed.retract:%s" % self.feed_name)
        self.assertEqual(self.feed.channel_edit,
                         "feed.edit:%s" % self.feed_name)
        self.assertEqual(self.feed.channel_publish,
                         "feed.publish:%s" % self.feed_name)

    ############################################################################
    #  Tests for config
    ############################################################################
    @defer.inlineCallbacks
    def testFeedSetGetConfig(self):
        # get an existing config
        ret = yield self.feed.get_config()
        self.assertEqual(ret, self.config)

        # set a config value
        new_conf = {"max_length": '20'}
        yield self.feed.set_config(new_conf)

        self.config.update(new_conf)

        ret = yield self.feed.get_config()
        self.assertEqual(ret, self.config)

    ############################################################################
    #  Tests for publish
    ############################################################################
    @defer.inlineCallbacks
    def testFeedPublish(self):
        item = "my beautiful item"
        feed = self.feed

        # no publishes (check on redis)
        n = yield self.pub.redis.get(feed.feed_publishes)
        self.assertFalse(n)

        id_ = yield feed.publish(item)

        # check on redis for new id
        ret = yield self.pub.redis.zrange(feed.feed_ids, 0, -1)
        self.assertTrue(ret, [id_])

        # check on redis for publishes increment
        n = yield self.pub.redis.get(feed.feed_publishes)
        self.assertEqual(n, '1')

        # check on redis for new item
        ret = yield self.pub.redis.hget(feed.feed_items, id_)
        self.assertEqual(ret[id_], item)

    @defer.inlineCallbacks
    def testFeedPublishWithMaxLength(self):
        import string

        items_01 = string.printable[0:20]
        ids_01 = map(str, range(0, len(items_01)))
        items_02 = string.printable[20:40]
        ids_02 = map(str, range(0, len(items_01)))

        feed = self.feed

        # set max_length
        feed.set_config({'max_length': '20'})

        for id_, item in zip(ids_01, items_01):
            yield feed.publish(item, id_)

        ret = yield feed.get_ids()
        self.assertEqual(set(ret), set(ids_01))

        for id_, item in zip(ids_02, items_02):
            yield feed.publish(item, id_)

        ret = yield feed.get_ids()
        self.assertEqual(set(ret), set(ids_01))

    ############################################################################
    #  Tests for has_id
    ############################################################################
    @defer.inlineCallbacks
    def testFeedHasId(self):
        item = "my beautiful item"
        id_ = "myid"
        feed = self.feed

        yield feed.publish(item, id_)

        ret = yield feed.has_id(id_)
        self.assertTrue(ret)

        # non existing item
        ret = yield feed.has_id(id_ + "123")
        self.assertFalse(ret)

    ############################################################################
    #  Tests for get*
    ############################################################################
    @defer.inlineCallbacks
    def testFeedGetItem(self):
        item = "my beautiful item"
        id_ = "myid"
        feed = self.feed

        yield feed.publish(item, id_)

        ret = yield feed.get_item(id_)
        self.assertEqual(ret, {id_: item})

        # non existing item
        ret = yield feed.get_item(id_ + "123")
        self.assertIsNone(ret)

    @defer.inlineCallbacks
    def testFeedGetIds(self):
        item = "my beautiful item"
        id_ = "myid"
        feed = self.feed

        yield feed.publish(item, id_)

        ret = yield feed.get_ids()
        self.assertEqual(ret, [id_])

    @defer.inlineCallbacks
    def testFeedGetAll(self):
        import string
        items = string.printable
        ids = map(str, range(0, len(items)))
        feed = self.feed
        for id_, item in zip(ids, items):
            yield feed.publish(item, id_)

        ret = yield feed.get_ids()
        self.assertEqual(set(ret), set(ids))

        ret = yield feed.get_all()
        ret_ids = ret.keys()
        ret_items = ret.values()
        self.assertEqual(set(ret_ids), set(ids))
        self.assertEqual(set(ret_items), set(items))


if __name__ == "__main__":
    pass
