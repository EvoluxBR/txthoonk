from zope.interface import implements #@UnresolvedImport

from twisted.internet.protocol import ReconnectingClientFactory

from txredis.protocol import Redis
from twisted.internet import interfaces

class Thoonk(object):
    implements(interfaces.IProtocol)
    redis = Redis() # pydev: force code completion
    def __init__(self, redis):
        self.redis = redis

    def dataReceived(self, data):
        """
        Called whenever data is received.

        Use this method to translate to a higher-level message.  Usually, some
        callback will be made upon the receipt of each complete protocol
        message.

        @param data: a string of indeterminate length.  Please keep in mind
            that you will probably need to buffer some data, as partial
            (or multiple) protocol messages may be received!  I recommend
            that unit tests for protocols call through to this method with
            differing chunk sizes, down to one byte at a time.
        """
        self.redis.dataReceived(data)

    def connectionLost(self, reason):
        """
        Called when the connection is shut down.

        Clear any circular references here, and any external references
        to this Protocol.  The connection has been closed. The C{reason}
        Failure wraps a L{twisted.internet.error.ConnectionDone} or
        L{twisted.internet.error.ConnectionLost} instance (or a subclass
        of one of those).

        @type reason: L{twisted.python.failure.Failure}
        """
        self.redis.connectionLost(reason)

    def makeConnection(self, transport):
        """
        Make a connection to a transport and a server.
        """
        self.redis.makeConnection(transport)

    def connectionMade(self):
        """
        Called when a connection is made.

        This may be considered the initializer of the protocol, because
        it is called when the connection is completed.  For clients,
        this is called once the connection to the server has been
        established; for servers, this is called after an accept() call
        stops blocking and a socket has been received.  If you need to
        send any greeting or initial message, do it here.
        """
        self.redis.connectionMade()

class ThoonkFactory(ReconnectingClientFactory):
    protocol = Redis
    protocol_wrapper = Thoonk

    def __init__(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs

    def buildProtocol(self, addr):
        """
        Called when a connection has been established to addr.

        If None is returned, the connection is assumed to have been refused,
        and the Port will close the connection.

        @type addr: (host, port)
        @param addr: The address of the newly-established connection

        @return: None if the connection was refused, otherwise an object
                 providing L{IProtocol}.
        """

        redis = self.protocol(*self._args, **self._kwargs)
        self.resetDelay()
        return self.protocol_wrapper(redis)

