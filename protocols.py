#!/usr/bin/env python3
# (c) 2021 Martin Kistler

from abc import ABC, abstractmethod
from enum import Enum
from os import linesep

from twisted.internet import reactor
from twisted.internet.error import ConnectionDone
from twisted.internet.protocol import Factory, Protocol
from twisted.logger import Logger
from twisted.protocols import basic
from twisted.python.failure import Failure

from models import Version, Message, VerAck, MessageError, GetAddr, NetworkAddress, Addr, Ping, Pong, ChatMessage


Factory.noisy = False


class States(Enum):
    """
    Enum class representing possible states of the PeerProtocol.
    """
    INIT = 0
    WAIT_FOR_VERSION = 1
    WAIT_FOR_VERACK = 2
    CON_ESTABLISHED = 3


class PeerProtocol(Protocol, ABC):
    log = Logger()

    def __init__(self, client: 'P2PClient'):
        self.client = client
        self.state = States.INIT
        self._peer = None

    @property
    def peer(self) -> NetworkAddress:
        if self._peer is None:
            peer = self.transport.getPeer()
            return NetworkAddress(peer.host, peer.port)
        else:
            return self._peer

    def connectionLost(self, reason: Failure = ConnectionDone):
        self.log.info(f'connection to Peer {self.peer} lost')
        self.log.debug('reason:' + str(reason))

        self.client.remove_connection(self)

    def dataReceived(self, data: bytes):
        try:
            message = Message.from_bytes(data)
        except MessageError:
            self.log.failure(f'Invalid message received from {self.peer}.')
            self.transport.loseConnection()
            return

        self.log.debug(f'Message received from {self.peer}')

        if isinstance(message, Version):
            self.handle_version(message)
        elif isinstance(message, VerAck):
            self.handle_verack(message)
        elif isinstance(message, GetAddr):
            self.handle_getadr(message)
        elif isinstance(message, Addr):
            self.handle_addr(message)
        elif isinstance(message, Ping):
            self.handle_ping(message)
        elif isinstance(message, Pong):
            self.handle_pong(message)
        elif isinstance(message, ChatMessage):
            self.handle_chat_message(message)

    def handle_chat_message(self, chat_message: ChatMessage):
        self.client.print_chat(chat_message)
        self.client.broadcast(chat_message, self.peer)
        self.log.info(f"broadcasting message")

    @abstractmethod
    def connectionMade(self):
        """
        What has to be done, when a new connection has been made depends on who initiated it.
        Subclasses must implement this.
        """
        self.log.debug(f'Connected to {self.peer}.')

    def handle_getadr(self, getadr: GetAddr):
        self.log.debug(f'Address request received from {self.peer}.')
        addr_msg = Addr(list(self.client.known_participants.values()))

    def handle_addr(self, addr: Addr):
        self.log.debug(f'Address information received from {self.peer}.')
        map(self.client.add_participant, addr.addresses)
        self.client.broadcast(addr, self.peer)

    def handle_ping(self, ping: Ping):
        self.log.debug(f'Ping message received from {self.peer}.')

    def handle_pong(self, pong: Pong):
        self.log.debug(f'Pong message received from {self.peer}.')

    def forward_message(self, message: Message):
        self.log.debug(f'Forwarding message to {self.peer}')
        self.transport.write(bytes(message))

    @abstractmethod
    def handle_version(self, version: Version):
        if self.state == States.WAIT_FOR_VERSION:
            if self.client.version_compatible(version.version) and self.client.nonce != version.nonce:
                self.transport.write(bytes(VerAck()))
                self.client.add_participant(version.addr_from)
                self._peer = version.addr_from
                self.client.add_connection(self)
                return

        self.transport.loseConnection()

    @abstractmethod
    def handle_verack(self, verack: VerAck):
        if self.state == States.WAIT_FOR_VERACK:
            self.log.debug(f'Version acknowledged by {self.peer}.')
            return

        self.transport.loseConnection()


class IncomingPeerProtocol(PeerProtocol):
    def connectionMade(self):
        super().connectionMade()

        self.state = States.WAIT_FOR_VERSION

    def handle_version(self, version: Version):
        super().handle_version(version)

        reactor.callLater(0.1, self.transport.write,
                          bytes(Version(self.client.version, version.addr_from, self.client.address, self.client.nonce)))
        self.state = States.WAIT_FOR_VERACK

    def handle_verack(self, verack: VerAck):
        super().handle_verack(verack)

        self.log.info(f'Connection to {self.peer} established.')
        self.state = States.CON_ESTABLISHED


class OutgoingPeerProtocol(PeerProtocol):
    log = Logger()

    def connectionMade(self):
        super().connectionMade()

        self.transport.write(bytes(Version(self.client.version, self.peer, self.client.address, self.client.nonce)))
        self.state = States.WAIT_FOR_VERACK

    def handle_version(self, version: Version):
        super().handle_version(version)

        self.log.info(f'Connection to {self.peer} established.')
        self.state = States.CON_ESTABLISHED

        reactor.callLater(0.1, self.transport.write, bytes(GetAddr()))

    def handle_verack(self, verack: VerAck):
        super().handle_verack(verack)

        self.state = States.WAIT_FOR_VERSION


class UserInput(basic.LineReceiver):
    delimiter = linesep.encode('utf-8')

    def __init__(self, client):
        self.client = client

    def lineReceived(self, line):
        if line.startswith(b'!'):
            self.client.handle_command(line[1:])
        else:
            self.client.send_chat(line)


class PeerFactory(Factory):
    protocol = NotImplemented

    def __init__(self, client: 'P2PClient'):
        self.client = client

    def buildProtocol(self, addr):
        return self.protocol(self.client)


class IncomingPeerFactory(PeerFactory):
    protocol = IncomingPeerProtocol


class OutgoingPeerFactory(PeerFactory):
    protocol = OutgoingPeerProtocol
