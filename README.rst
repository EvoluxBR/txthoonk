txthoonk
========

Thoonk is a persistent (and fast!) system for push feeds, queues, and jobs 
which leverages Redis. txThoonk is the Python/Twisted implementation of 
Thoonk and it is interoperable with other versions of Thoonk (Thoonk.js 
and Thoonk.py).

Feed Types
----------

Feed
^^^^

*Status*: Implemented since version 0.1

The core of Thoonk is the feed. A feed is a subject that you can publish items
to (string, binary, json, xml, whatever), each with a unique id (assigned or
generated). Other apps and services may subscribe to your feeds and recieve
new/update/retract notices on your feeds. Each feed persists published items
that can later be queried. Feeds may also be configured for various behaviors,
such as max number of items, default serializer, friendly title, etc.

Feeds are useful for clustering applications, delivering data from different
sources to the end user, bridged peering APIs (pubsub hubbub, XMPP Pubsub,
maintaining ATOM and RSS files, etc), persisting, application state,
passing messages between users, taking input from and serving multiple APIs
simultaneously, and generally persisting and pushing data around.

Queue
^^^^^

*Status*: Unimplemented, planned to 0.2

Queues are stored and interacted with in similar ways to feeds, except instead
of publishes being broadcast, clients may do a "blocking get" to claim an item,
ensuring that they're the only one to get it. When an item is delivered, it is
deleted from the queue.

Queues are useful for direct message passing.

Sorted Feed
^^^^^^^^^^^

*Status*: Unimplemented, planned to 0.3

Sorted feeds are unbounded, manually ordered collections of items. Sorted feeds
behave similarly to plain feeds except that items may be edited in place or
inserted in arbitrary order.

Job
^^^

*Status*: Unimplemented, planned to 0.4

Jobs are like Queues in that one client claims an item, but that client is also
required to report that the item is finished or cancel execution. Failure to to
finish the job in a configured amount of time or canceling the job results in
the item being reintroduced to the available list. Unlike queues, job items are
not deleted until they are finished.

Jobs are useful for distributing load, ensuring a task is completed regardless
of outages, and keeping long running tasks away from synchronous interfaces.


Installation 
------------

Use pypi packages::

    pip install txthoonk

Requirements
------------

txThoonk requires the txredis package and (of course) twisted package::

    pip install twisted
    pip install txredis


Running the Tests
-----------------
In order run tests you need a redis server running on localhost:6381.
You can use our supplied redis.conf::
    
    redis-server tests/redis.conf

After start redis, you can run::

    trial tests/


Using txThoonk
--------------

See ``examples/*.py``


References and other implementations
------------------------------------

Read more about Thoonk at http://blog.thoonk.com


Thoonk.js
^^^^^^^^^

Thoonk.js is the NodeJS reference implementaion of Thoonk

http://github.com/andyet/thoonk.js

Thoonk.py
^^^^^^^^^

Thoonk.py is the pure python reference implementaion of Thoonk

http://github.com/andyet/thoonk.py

