#!/usr/bin/env python3
# (c) 2021 Martin Kistler

from abc import ABC, abstractmethod
from enum import Enum

from twisted.internet import reactor
from twisted.internet.error import ConnectionDone
from twisted.internet.protocol import Factory
from twisted.internet.protocol import Protocol
from twisted.logger import Logger
from twisted.python.failure import Failure

from models import Version, Message, VerAck, MessageError, GetAddr, NetworkAddress, Addr, Ping, Pong


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

    @property
    def peer_address(self) -> NetworkAddress:
        peer = self.transport.getPeer()
        return NetworkAddress(peer.host, peer.port)

    #@property
    #def host_address(self) -> NetworkAddress:
    #    host = self.transport.getHost()
    #    return NetworkAddress(host.host, host.port)

    def connectionLost(self, reason: Failure = ConnectionDone):
        self.log.info(f'Connection to Peer {self.peer_address} lost:\n {reason}')
        self.client.remove_participant(self.peer_address)

    def dataReceived(self, data: bytes):
        try:
            message = Message.from_bytes(data)
        except MessageError:
            self.log.failure(f'Invalid message received from {self.peer_address}.')
            self.transport.loseConnection()
            return

        self.log.info(f'Current state is {self.state}.')
        self.log.info(f'Message received from {self.peer_address}:\n{message}')

        if self.state != States.CON_ESTABLISHED:
            self.handle_handshake(message)
        else:
            if isinstance(message, GetAddr):
                self.handle_getadr(message)
            elif isinstance(message, Addr):
                self.handle_addr(message)
            elif isinstance(message, Ping):
                self.handle_ping(message)
            elif isinstance(message, Pong):
                self.handle_pong(message)

    @abstractmethod
    def connectionMade(self):
        """
        What has to be done, when a new connection has been made depends on who initiated it.
        Subclasses must implement this.
        """
        self.log.info(f'Connected to {self.peer_address}.')
        self.client.add_participant(self.peer_address)
        # self.client.add_participant(self.host_address)

    @abstractmethod
    def handle_handshake(self, message: Message):
        """
        Handshake handling depends on who initiated the connection.
        Subclasses must implement this.
        """
        return NotImplemented

    def handle_getadr(self, getadr: GetAddr):
        self.log.info(f'Address request received from {self.peer_address}.')
        self.transport.write(bytes(Addr(list(self.client.known_participants.values()))))

    def handle_addr(self, addr: Addr):
        self.log.info(f'Address information received from {self.peer_address}.')
        map(self.client.add_participant, addr.addresses)

    def handle_ping(self, ping: Ping):
        self.log.info(f'Ping message received from {self.peer_address}.')

    def handle_pong(self, pong: Pong):
        self.log.info(f'Pong message received from {self.peer_address}.')

    def forward_message(self, message: Message):
        self.log.info(f'Forwarding message to {self.peer_address}')
        self.transport.write(bytes(message))


class IncomingPeerProtocol(PeerProtocol):
    def connectionMade(self):
        super().connectionMade()

        self.client.add_incoming_connection(self.peer_address)
        self.state = States.WAIT_FOR_VERSION

    def connectionLost(self, reason: Failure = ConnectionDone):
        super().connectionLost(reason)

        self.client.remove_incoming_connection(self.peer_address)

    def handle_handshake(self, message: Message):
        if self.state == States.WAIT_FOR_VERSION:
            if isinstance(message, Version):
                if self.client.version_compatible(message.version) and self.client.nonce != message.nonce:
                    self.transport.write(bytes(VerAck()))
                    reactor.callLater(0.1, self.transport.write, bytes(Version(self.client.version, self.peer_address, self.host_address, self.client.nonce)))
                    self.state = States.WAIT_FOR_VERACK
                else:
                    self.transport.loseConnection()
            else:
                self.transport.loseConnection()

        elif self.state == States.WAIT_FOR_VERACK:
            if isinstance(message, VerAck):
                self.log.info(f'Version acknowledged by {self.peer_address}.')
                self.log.info(f'Handshake with {self.peer_address} finished successfully.')
                self.state = States.CON_ESTABLISHED
            else:
                self.transport.loseConnection()


class OutgoingPeerProtocol(PeerProtocol):
    log = Logger()

    def connectionMade(self):
        super().connectionMade()

        self.client.add_outgoing_connection(self.peer_address)
        self.transport.write(bytes(Version(self.client.version, self.peer_address, self.host_address, self.client.nonce)))
        self.state = States.WAIT_FOR_VERACK

    def connectionLost(self, reason: Failure = ConnectionDone):
        super().connectionLost(reason)

        self.client.remove_outgoing_connection(self.peer_address)

    def handle_handshake(self, message: Message):
        if self.state == States.WAIT_FOR_VERACK:
            if isinstance(message, VerAck):
                self.log.info(f'Version acknowledged by {self.peer_address}.')
                self.state = States.WAIT_FOR_VERSION
            else:
                self.transport.loseConnection()

        elif self.state == States.WAIT_FOR_VERSION:
            if isinstance(message, Version):
                if self.client.version_compatible(message.version) and self.client.nonce != message.nonce:
                    self.transport.write(bytes(VerAck()))
                    self.log.info(f'Handshake with {self.peer_address} finished successfully.')
                    self.state = States.CON_ESTABLISHED
                    reactor.callLater(0.1, self.transport.write, bytes(GetAddr()))
                else:
                    self.transport.loseConnection()
            else:
                self.transport.loseConnection()


class PeerFactory(Factory):
    protocol = NotImplemented
    noisy = False

    def __init__(self, client: 'P2PClient'):
        self.client = client

    def buildProtocol(self, addr):
        return self.protocol(self.client)


class IncomingPeerFactory(PeerFactory):
    protocol = IncomingPeerProtocol


class OutgoingPeerFactory(PeerFactory):
    protocol = OutgoingPeerProtocol
