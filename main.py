#!/usr/bin/env python3
# (c) 2021 Martin Kistler

from twisted.internet.protocol import Factory
from twisted.internet.protocol import Protocol

from models import Version, Message, VerAck

VERSION = 0


def address_to_bytes(address: str) -> bytes:
    """Returns the values of a dot-seperated (IPv4) address in str-format as bytes.
    for instance: 127.0.0.1 -> \x7f\x00\x00\x01"""
    return bytes(int(val) for val in address.split('.'))


class Peer(Protocol):
    def __init__(self):
        self.state = 'HANDSHAKE'
        self.peer_address = None
        self.host_address = None

    def connectionMade(self):
        self.peer_address = address_to_bytes(self.transport.getPeer().host)
        self.host_address = address_to_bytes(self.transport.getHost().host)

    def dataReceived(self, data: bytes):
        message = Message.from_bytes(data)

        if self.state == 'HANDSHAKE':
            self.handle_handshake(message)
        elif self.state == 'CONNECTION_ESTABLISHED':
            print('CONNECTION_ESTABLISHED')

    def handle_handshake(self, message):
        if isinstance(message, Version):
            if message.version == VERSION:
                self.transport.write(bytes(VerAck()))
                self.transport.write(bytes(Version(
                    VERSION,
                    self.peer_address,
                    self.host_address
                )))


class PeerFactory(Factory):
    protocol = Peer

    def __init__(self, config):
        self.config = config

        self.active_peers = {}
        self.global_participants = {}

    def buildProtocol(self, addr):
        return Peer()
