'''
Created on Jul 6, 2012

@author: iuri
'''
from twisted.internet import defer
import uuid
import time

class Feed(object):
    """
    A Thoonk feed is a collection of items ordered by publication date.

    The collection may either be bounded or unbounded in size. A bounded
    feed is created by adding the field 'max_length' to the configuration
    with a value greater than 0.

    Attributes:
        pub             - The main ThoonkPub object.
        name            - The name of this feed.
        feed_ids        - Redis key for a sorted set of item IDs.
        feed_items      - Redis key for a hash table of items keyed by ID.
        feed_publishes  - Redis key for a counter for number of published items.
        feed_config     - Redis key for the configuration data of this feed.
        channel_retract - Redis pubsub channel for publication notices.
        channel_edit    - Redis pubsub channel for retraction notices.
        channel_publish - Redis pubsub channel for edit notices.

    Redis Keys Used:
        feed.ids:[feed]       -- A sorted set of item IDs.
        feed.items:[feed]     -- A hash table of items keyed by ID.
        feed.config:[feed]    -- Feed configuration data of this feed.
        feed.publishes:[feed] -- A counter for number of published items.
        feed.publish:[feed]   -- A pubsub channel for publication notices.
        feed.retract:[feed]   -- A pubsub channel for retraction notices.
        feed.edit:[feed]      -- A pubsub channel for edit notices.

    Thoonk Standard API:
        get_ids -- Return the IDs of all items in the feed.
        get_item -- Return a single item from the feed given its ID.
        get_all -- Return all items in the feed.
        publish -- Publish a new item to the feed, or edit an existing item.
        retract -- Remove an item from the feed.
    """
    def __init__(self, pub, name):
        '''
        Create a new Feed object for a given Thoonk feed name.

        @param pub: the ThoonkPub object
        @param name: the name of this feed
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
        '''
        Get the configuration dictionary of this feed.
        '''
        return self.pub.get_config(self.name)

    def set_config(self, conf):
        '''
        Set configuration of this feed.

        @param conf: the configuration dictionary.
        '''
        return self.pub.set_config(self.name, conf)

    def publish(self, item, id_=None):
        '''
        Publish an item to the feed, or replace an existing item.

        Newly published items will be at the top of the feed, while
        edited items will remain in their original order.

        If the feed has a max length, then the oldest entries will
        be removed to maintain the maximum length.

        @param item: A string representation of the item.
        @param id_: Optional id of this item.
        '''
        pub = self.pub
        redis = pub.redis

        if id_ is None:
            id_ = uuid.uuid4().hex

        id_ = str(id_)

        def _check_exec(bulk_result):
            """
            Called when redis exec is completed

            Will emit a publish or an edit event.
            """
            # All defers must be succeed
            assert all([a[0] for a in bulk_result])

            multi_result = bulk_result[-1][1]
            if multi_result:
                # Transaction done :D
                # assert number commands in transaction
                assert len(multi_result) >= 3
                # check if id_ existed when added
                non_exists = multi_result[-1]
                if non_exists:
                    d = pub.publish_channel(self.channel_publish, id_, item)
                else:
                    d = pub.publish_channel(self.channel_edit, id_, item)

                # return the id
                d.addCallback(lambda x: id_)
                return d

            # Transaction fail :(
            # repeat it
            return self.publish(item, id_)

        def _do_publish(delete_ids, has_id):
            """
            Called when we have ids to be deleted

            Will add related data over the keys of redis.

            May emit a retract event if has items to be deleted
            """
            defers = []

            # begin transaction
            defers += [redis.multi()]

            # delete ids
            # id is already on feed, we don't need to delete one
            if has_id and len(delete_ids) > 0:
                try:
                    # try to choose itself if marked to be deleted
                    delete_ids.remove(id_)
                except ValueError:
                    # else remove the last
                    delete_ids.pop()

            for i in delete_ids:
                defers += [redis.zrem(self.feed_ids, i)]
                defers += [redis.hdel(self.feed_items, i)]
                defers += [pub.publish_channel(self.channel_retract, i)]

            defers += [redis.incr(self.feed_publishes)] # -3
            defers += [redis.hset(self.feed_items, id_, item)] # -2
            defers += [redis.zadd(self.feed_ids, id_, time.time())] # -1

            defers += [redis.execute()]

            return defer.DeferredList(defers).addCallback(_check_exec)

        def _got_config(bulk_result):
            """
            Called when we have this feed configuration

            May generate a list of ids to be deleted.
            """
            # All defers must be succeed
            assert all([a[0] for a in bulk_result])
            # assert number of commands
            assert len(bulk_result) == 5

            has_id = bulk_result[-2][1]
            config = bulk_result[-1][1]
            max_ = config.get("max_length")
            if max_ is not None and max_.isdigit() and int(max_) > 0:
                # get ids to be deleted
                d = redis.zrange(self.feed_ids, 0, -int(max_))
            else:
                # no ids to be deleted
                d = defer.succeed([])

            return d.addCallback(_do_publish, has_id)

        defers = []
        defers.append(redis.watch(self.feed_config)) #0
        defers.append(redis.watch(self.feed_ids)) #1
        defers.append(redis.watch(self.feed_items)) #2
        defers.append(self.has_id(id_)) #3
        defers.append(self.get_config()) #4
        return defer.DeferredList(defers).addCallback(_got_config)

    def retract(self, id_):
        '''
        Remove an item from the feed.

        @param id_: The ID value of the item to remove.
        '''
        pub = self.pub
        redis = pub.redis

        def _check_exec(multi_result):
            """
            Called when redis exec is completed
            """

            if multi_result:
                # transaction done :D
                # assert number commands in transaction
                assert len(multi_result) == 3
                return defer.succeed(None)

            # Transaction fail :(
            # repeat it
            return self.retract(id_)

        def _has_id(has_id):
            """
            Called when self.has_id is completed
            """
            if not has_id:
                return redis.unwatch()
            # start transaction
            d = redis.multi()
            d.addCallback(lambda x: redis.zrem(self.feed_ids, id_))
            d.addCallback(lambda x: redis.hdel(self.feed_items, id_))
            d.addCallback(lambda x: pub.publish_channel(self.channel_retract,
                                                        id_))
            d.addCallback(lambda x: redis.execute())

            d.addCallback(_check_exec)
            return d

        d = redis.watch(self.feed_items)
        d.addCallback(lambda x: redis.watch(self.feed_items))
        d.addCallback(lambda x: redis.watch(self.feed_ids))
        d.addCallback(lambda x: self.has_id(id_))
        d.addCallback(_has_id)

        return d

    def get_item(self, id_):
        '''
        Retrieve a single item from the feed.

        @param id_: The ID of the item to retrieve.
        '''
        return self.pub.redis.hget(self.feed_items, id_)

    def get_id(self, id_):
        '''
        Retrieve a single item from the feed.

        It is just an alias to get_item.

        @param id_: The ID of the item to retrieve.
        '''
        return self.get_item(id_)

    def has_id(self, id_):
        '''
        Verify if the feed has an item ID.

        @param id_: The ID of the item to retrieve.
        '''
        # ZRank has complexity O(log(n))
        #d = self.pub.redis.zrank(self.feed_ids, id_)
        #d.addCallback(lambda i: i is not None)

        # HExists has complexity O(1)
        d = self.pub.redis.hexists(self.feed_items, id_)
        return d

    def get_ids(self):
        '''
        Return the set of IDs used by items in the feed.
        '''
        return self.pub.redis.zrange(self.feed_ids, 0, -1)

    def get_all(self):
        '''
        Return all items from the feed.
        '''
        return self.pub.redis.hgetall(self.feed_items)
