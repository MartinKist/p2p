#!/usr/bin/env python3
# (c) 2021 Martin Kistler
import random

from twisted.internet import reactor, task
from twisted.internet.endpoints import TCP4ServerEndpoint, TCP4ClientEndpoint
from twisted.logger import Logger
from twisted.python.failure import Failure

import defaults
from models import NetworkAddress
from protocols import IncomingPeerFactory, OutgoingPeerFactory, PeerProtocol


class P2PClient:
    log = Logger()

    def __init__(self, ipv4_adr: str, port: int, outgoing: int):
        self.version = 0

        self.address = NetworkAddress(ipv4_adr, port)
        self.port = port
        self.outgoing = outgoing

        # These dicts have the form {'0.0.0.0:1111': NetworkAddress}
        self.default_peers = defaults.PEERS
        self.known_participants = self.default_peers.copy()    # participants of the network this client knows about
        self.connections = {}       # direct connections this client maintains

        self.nonce = random.randbytes(8)    # random nonce used to detect connections to self

    def version_compatible(self, peer_version: int) -> bool:
        """
        Determine if the version of a peer's client is compatible with this client's version.
        """
        return peer_version == self.version

    def add_participant(self, participant: NetworkAddress):
        """
        Add a new network participant to this client's record of known network participants.
        :param participant: The NetworkAddress representing the participant to add.
        """
        self.known_participants.update({str(participant): participant})

    def remove_participant(self, participant: NetworkAddress):
        """
        Remove a network participant from this client's record of known network participants.
        :param participant: The NetworkAddress representing the participant to remove.
        """
        if str(participant) in self.known_participants:
            del self.known_participants[str(participant)]

    def add_connection(self, connection: PeerProtocol):
        self.connections.update({str(connection.peer): connection})

    def remove_connection(self, connection: PeerProtocol):
        if str(connection.peer) in self.connections:
            del self.connections[str(connection.peer)]

    def make_new_connection(self):
        """
        Try to establish a new outgoing connection to a random known network participant.
        """
        for addr, netw_addr in self.known_participants.items():
            if addr not in self.connections:
                self.connect(netw_addr)
                break
        else:
            for addr, netw_addr in self.default_peers.items():
                if addr not in self.connections:
                    self.connect(netw_addr)
                    break

    def connect(self, peer: NetworkAddress):
        """
        Try to connect to a new peer.
        :param peer: The NetworkAddress representing the peer.
        """
        endpoint = TCP4ClientEndpoint(reactor, peer.address, peer.port)
        attempt = endpoint.connect(OutgoingPeerFactory(self))

        attempt.addCallback(self.on_connect_success, peer)
        attempt.addErrback(self.on_connect_error, peer)
        reactor.callLater(30, attempt.cancel)   # Timeout

    def on_connect_success(self, result, peer: NetworkAddress):
        self.log.debug(f'successfully connected to {peer}')

    def on_connect_error(self, reason: Failure, participant: NetworkAddress):
        self.log.info(f'connection to {participant} failed:\n' + str(reason.args[0]))
        self.remove_participant(participant)

    def check_connections(self):
        """
        Check the health of this client's connections and attempt to make new connections if the desired amount of
        outgoing connections is not reached.
        """
        self.log.info(f'Connected to {len(self.connections)} peers')
        self.log.debug('I know of the following participants: \n' + '\n'.join(adr for adr in self.known_participants))

        if len(self.connections) < self.outgoing:
            self.make_new_connection()

    def run(self):
        task.LoopingCall(self.check_connections).start(10)

        endpoint = TCP4ServerEndpoint(reactor, self.port)
        endpoint.listen(IncomingPeerFactory(self))

        reactor.run()
