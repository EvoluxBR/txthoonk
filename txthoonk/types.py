'''
Created on Jul 6, 2012

@author: iuri
'''
from twisted.internet import defer
import uuid
import time

class Feed(object):
    '''
    classdocs
    '''
    def __init__(self, pub, name):
        '''
        Constructor
        '''
        self.pub = pub
        self.name = name

        self.feed_ids = 'feed.ids:%s' % name
        self.feed_items = 'feed.items:%s' % name
        self.feed_publishes = 'feed.publishes:%s' % name
        self.feed_config = 'feed.config:%s' % name

        self.channel_retract = 'feed.retract:%s' % name
        self.channel_edit = 'feed.edit:%s' % name
        self.channel_publish = 'feed.publish:%s' % name

    def get_config(self):
        return self.pub.get_config(self.name)

    def set_config(self, conf):
        return self.pub.set_config(self.name, conf)

    def publish(self, item, id_=uuid.uuid4().hex):
        pub = self.pub
        redis = pub.redis

        def _check_exec(bulk_result):
            # All defers must be succeed
            assert all([a[0] for a in bulk_result])

            multi_result = bulk_result[-1][1]
            if multi_result:
                # Transaction done :D
                # assert number commands in transaction
                assert len(multi_result) >= 3
                # check if feed_name existed when was deleted
                non_exists = multi_result[-1]
                if non_exists:
                    d = pub._publish_channel(self.channel_publish, id_, item)
                else:
                    d = pub._publish_channel(self.channel_edit, id_, item)

                # return the id
                d.addCallback(lambda x: id_)
                return d

            # Transaction fail :(
            # repeat it
            return self.publish(item, id_)

        def _do_publish(delete_ids):
            defers = []

            # begin transaction
            defers += [redis.multi()]

            # delete ids
            for i in delete_ids:
                if i == id_:
                    continue
                defers += [redis.zrem(self.feed_ids, i)]
                defers += [redis.hel(self.feed_items, i)]
                defers += [pub._publish_channel(self.channel_retract, id)]

            defers += [redis.incr(self.feed_publishes)] # -3
            defers += [redis.hset(self.feed_items, id_, item)] # -2
            defers += [redis.zadd(self.feed_ids, id_, time.time())] # -1

            defers += [redis.execute()]

            return defer.DeferredList(defers).addCallback(_check_exec)

        def _got_config(bulk_result):
            # All defers must be succeed
            assert all([a[0] for a in bulk_result])
            # assert number of commands
            assert len(bulk_result) == 3

            config = bulk_result[-1][1]
            max_ = config.get("max_length")
            if max_ is not None:
                # get ids to be deleted
                d = redis.zrange(self.feed_ids, 0, -(max + 1))
            else:
                # no ids to be deleted
                d = defer.succeed([])
            return d.addCallback(_do_publish)

        defers = []
        defers.append(redis.watch(self.feed_config)) #0
        defers.append(redis.watch(self.feed_ids)) #1
        defers.append(self.get_config()) #2
        return defer.DeferredList(defers).addCallback(_got_config)

    def get_item(self, id_):
        return self.pub.redis.hget(self.feed_items, id_)
