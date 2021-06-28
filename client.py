#!/usr/bin/env python3
# (c) 2021 Martin Kistler

from twisted.internet import reactor
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet.protocol import Factory
from twisted.internet.protocol import Protocol
from twisted.logger import Logger

from models import Version, Message, VerAck, MessageError, GetAddr, NetworkAddress
from protocols import IncomingPeerFactory


class P2PClient:
    def __init__(self, config: dict):
        self.version = 0
        self.port = config['port']
        self.known_participants = {}

    def version_compatible(self, peer_version: int) -> bool:
        """
        Determines if the version of a peer's client is compatible with this client's version.
        """
        return peer_version == self.version

    def add_participant(self, participant_addr: NetworkAddress):
        self.known_participants.update({participant_addr.address: participant_addr})

    def remove_participant(self, participant_addr: NetworkAddress):
        if participant_addr.address in self.known_participants:
            del self.known_participants[participant_addr.address]

    def bootstrap(self):
        pass

    def run(self):
        self.bootstrap()
        endpoint = TCP4ServerEndpoint(reactor, self.port)
        endpoint.listen(IncomingPeerFactory(self))

        reactor.run()
