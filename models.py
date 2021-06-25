#!/usr/bin/env python3
# (c) 2021 Martin Kistler

from __future__ import annotations

import time
from abc import ABC
from enum import Enum
from hashlib import sha256
from typing import Union


BYTEORDER = 'little'


class MessageType(Enum):
    version = b'version'
    verack = b'verack'


class IPVersion(Enum):
    IPv4 = 4
    IPv6 = 6


class ChecksumError(Exception):
    def __init__(self, msg_type: MessageType, length: int, checksum: bytes, payload: bytes):
        self.msg_type = msg_type
        self.length = length
        self.checksum = checksum
        self.payload = payload


class StructABC(ABC):
    def __bytes__(self):
        return NotImplemented

    @classmethod
    def from_bytes(cls, data: bytes):
        return NotImplemented

    def __eq__(self, other):
        return bytes(self) == bytes(other)

    def __str__(self):
        return str(bytes(self))


class Message(StructABC):
    # TODO: write down specification
    # https://en.bitcoin.it/wiki/Protocol_documentation#Common_structures

    def __init__(self, msg_type: Union[MessageType, bytes], payload: bytes):
        self.msg_type = msg_type
        self.payload = payload

    def __bytes__(self) -> bytes:
        return bytes(self.msg_type.value).ljust(12, b'\0') \
               + len(self.payload).to_bytes(4, BYTEORDER) \
               + sha256(sha256(self.payload).digest()).digest()[:4] \
               + self.payload

    @classmethod
    def from_bytes(cls, data: bytes) -> Message:
        msg_type = MessageType(data[:12].rstrip(b'\0'))
        length = data[12:16]
        checksum = data[16:20]
        payload = data[20:]

        if not sha256(sha256(payload).digest()).digest()[:4] == checksum:
            raise ChecksumError(msg_type, length, checksum, payload)
        else:
            return cls(msg_type, payload)


class NetworkAddress(StructABC):
    def __init__(self, ip_version: IPVersion, address: bytes, port: int, timestamp: int = None):
        self.ip_version = ip_version
        self.port = port

        if self.ip_version == IPVersion.IPv4:
            self.address = b'\0' * 10 + b'\255' * 2 + address
        else:
            self.address = address

        if timestamp is None:
            self.timestamp = int(time.time())
        else:
            self.timestamp = timestamp

    def __bytes__(self) -> bytes:
        return self.timestamp.to_bytes(4, BYTEORDER) \
               + self.address \
               + self.port.to_bytes(2, BYTEORDER)
