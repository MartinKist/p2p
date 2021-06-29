#!/usr/bin/env python3
# (c) 2021 Martin Kistler
import random

from twisted.internet import reactor, task
from twisted.internet.endpoints import TCP4ServerEndpoint, TCP4ClientEndpoint
from twisted.internet.protocol import Factory
from twisted.internet.protocol import Protocol
from twisted.logger import Logger
from twisted.python.failure import Failure

import defaults
from models import Version, Message, VerAck, MessageError, GetAddr, NetworkAddress
from protocols import IncomingPeerFactory, OutgoingPeerFactory


class P2PClient:
    log = Logger()

    def __init__(self, port: int, outgoing: int):
        self.version = 0
        self.port = port
        self.outgoing = outgoing

        # These dicts have the form {str(NetworkAddress): NetworkAddress}
        self.default_peers = defaults.PEERS
        self.known_participants = self.default_peers.copy()    # participants of the network this client knows about
        self.outgoing_cons = {}     # connections made by this client to another client
        self.incoming_cons = {}     # connections made by another client to this client

        self.nonce = random.randbytes(8)    # random nonce used to detect connections to self

    @property
    def connections(self) -> dict:
        cons = self.outgoing_cons.copy()
        cons.update(self.incoming_cons)
        return cons

    def version_compatible(self, peer_version: int) -> bool:
        """
        Determine if the version of a peer's client is compatible with this client's version.
        """
        return peer_version == self.version

    def add_participant(self, participant: NetworkAddress):
        """
        Adds a new network participant to this client's record of known network participants.
        :param participant: The NetworkAddress representing the participant to add.
        """
        self.known_participants.update({str(participant): participant})

    def remove_participant(self, participant: NetworkAddress):
        """
        Removes a network participant from this client's record of known network participants.
        :param participant: The NetworkAddress representing the participant to remove.
        """
        if participant.address in self.known_participants:
            del self.known_participants[str(participant)]

    def make_new_connection(self):
        """
        Try to establish a new outgoing connection to a random known network participant.
        """
        for addr, netw_addr in self.known_participants.items():
            if addr not in self.outgoing_cons:
                self.connect(netw_addr)
                break
        else:
            for addr, netw_addr in self.default_peers.items():
                if addr not in self.outgoing_cons:
                    self.connect(netw_addr)
                    break

    def connect(self, peer: NetworkAddress):
        """
        Try to connect to a new peer.
        :param peer: The NetworkAddress representing the peer.
        """
        endpoint = TCP4ClientEndpoint(reactor, str(peer), peer.port)
        attempt = endpoint.connect(OutgoingPeerFactory(self))
        attempt.addCallback(self.on_connect_success)
        attempt.addErrback(self.on_connect_error, peer)
        reactor.callLater(30, attempt.cancel)   # Timeout

    def on_connect_success(self):
        self.check_connections()

    def on_connect_error(self, reason: Failure, netw_addr: NetworkAddress):
        self.log.info('connection failed:\n' + str(reason))
        if netw_addr in self.known_participants:
            del self.known_participants[str(netw_addr)]

    def check_connections(self):
        """
        Check the health of this client's connections and attempt to make new connections if the desired amount of
        outgoing connections is not reached.
        """
        self.log.info(f'Connected to {len(self.connections)} peers')
        if len(self.outgoing_cons) < self.outgoing:
            self.make_new_connection()

    def run(self):
        task.LoopingCall(self.check_connections).start(30)

        endpoint = TCP4ServerEndpoint(reactor, self.port)
        endpoint.listen(IncomingPeerFactory(self))

        reactor.run()
