'''
Created on Jul 6, 2012

@author: iuri
'''

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

