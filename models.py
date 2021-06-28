#!/usr/bin/env python3
# (c) 2021 Martin Kistler

from __future__ import annotations

import random
import time
from abc import ABC, abstractmethod
from hashlib import sha256
from typing import Union

BYTEORDER = 'little'


def calculate_checksum(data: bytes) -> bytes:
    return sha256(sha256(data).digest()).digest()[:4]


class MessageError(Exception):
    def __init__(self, msg_type: bytes, length: int, checksum: bytes, payload: bytes):
        self.msg_type = msg_type
        self.length = length
        self.checksum = checksum
        self.payload = payload

        # TODO: add description parameter


class StructABC(ABC):
    @abstractmethod
    def __bytes__(self) -> bytes:
        return NotImplemented

    @classmethod
    @abstractmethod
    def from_bytes(cls, data: bytes):
        return NotImplemented

    def __eq__(self, other):
        return bytes(self) == bytes(other)

    def __str__(self):
        return str(bytes(self).hex(' '))


class VarInt:
    def __init__(self, value: Union[int, bytes]):
        if isinstance(value, int):
            self.value = value
        elif isinstance(value, bytes):
            if self.get_length(value[0]) != 1:
                value = value[1:]
            self.value = int.from_bytes(value, BYTEORDER)

    @property
    def __len__(self) -> int:
        """Returns the number of bytes this VarInt has, including prefix, if existent."""
        return len(bytes(self))

    @staticmethod
    def get_length(first_byte: int) -> int:
        """Returns the expected length of the VarInt, by examining the first byte."""
        if first_byte < 253:
            return 1
        elif first_byte == 253:
            return 3
        elif first_byte == 254:
            return 5
        elif first_byte == 255:
            return 9
        else:
            raise ValueError

    def __bytes__(self) -> bytes:
        if self.value <= int('fc', 16):
            return self.value.to_bytes(1, BYTEORDER)
        elif self.value <= int('ffff', 16):
            return b'\xfd' + self.value.to_bytes(2, BYTEORDER)
        elif self.value <= int('ffffffff', 16):
            return b'\xfe' + self.value.to_bytes(4, BYTEORDER)
        elif self.value <= int('ffffffffffffffff', 16):
            return b'\xff' + self.value.to_bytes(8, BYTEORDER)
        else:
            raise OverflowError

    def __int__(self) -> int:
        return self.value


class Message(StructABC, ABC):
    # TODO: write down specification
    # https://en.bitcoin.it/wiki/Protocol_documentation#Common_structures

    @property
    @abstractmethod
    def message_type(self) -> bytes:
        return NotImplemented

    @property
    @abstractmethod
    def payload(self) -> bytes:
        return NotImplemented

    @property
    def checksum(self) -> bytes:
        return calculate_checksum(self.payload)

    @property
    def length(self) -> int:
        return len(self.payload)

    def __bytes__(self) -> bytes:
        return self.message_type \
               + self.length.to_bytes(4, BYTEORDER) \
               + self.checksum \
               + self.payload

    @classmethod
    @abstractmethod
    def from_bytes(cls, data: bytes) -> Message:
        msg_type = data[:12].rstrip(b'\0')
        length = int.from_bytes(data[12:16], BYTEORDER)
        checksum = data[16:20]
        payload = data[20:20 + length]

        if calculate_checksum(payload) == checksum and msg_type in message_types:
            return message_types[msg_type].from_bytes(payload)
        else:
            raise MessageError(msg_type, length, checksum, payload)

    def __str__(self):
        return f'Message type: {self.message_type}\n' \
               + f'Payload length: {len(self.payload)}\n' \
               + f'Checksum: {self.checksum}\n' \
               + 'Payload:\n' \
               + str(self.payload)


class NetworkAddress(StructABC):
    def __init__(self, address: bytes, port: int, timestamp: int = None):
        self.address = address
        self.port = port

        if timestamp is None:
            self.timestamp = int(time.time())
        else:
            self.timestamp = timestamp

        # if address is 4 bytes long it is an IPv4-address
        if len(self.address) == 4:
            self.address = b'\0' * 10 + b'\xff' * 2 + self.address

    def __bytes__(self) -> bytes:
        return self.timestamp.to_bytes(4, BYTEORDER) \
               + self.address \
               + self.port.to_bytes(2, BYTEORDER)

    @classmethod
    def from_bytes(cls, data: bytes) -> NetworkAddress:
        timestamp = int.from_bytes(data[:4], BYTEORDER)
        address = data[4:20]
        port = int.from_bytes(data[20:22], BYTEORDER)

        return cls(address, port, timestamp)


class Version(Message):
    def __init__(self, version: int, addr_recv: NetworkAddress, addr_from: NetworkAddress, timestamp: int = None):
        self.version = version
        self.addr_recv = addr_recv
        self.addr_from = addr_from

        if timestamp is None:
            self.timestamp = int(time.time())
        else:
            self.timestamp = timestamp

    @property
    def message_type(self) -> bytes:
        return b'version'.ljust(12, b'\0')

    @property
    def payload(self) -> bytes:
        return self.version.to_bytes(4, BYTEORDER) \
               + self.timestamp.to_bytes(8, BYTEORDER) \
               + bytes(self.addr_recv) \
               + bytes(self.addr_from)

    @classmethod
    def from_bytes(cls, data: bytes) -> Version:
        version = int.from_bytes(data[:4], BYTEORDER)
        timestamp = int.from_bytes(data[4:12], BYTEORDER)
        addr_recv = NetworkAddress.from_bytes(data[12:34])
        addr_from = NetworkAddress.from_bytes(data[34:56])

        return cls(version, addr_recv, addr_from, timestamp)


class Ping(Message):
    def __init__(self, nonce: bytes = None):
        if nonce is None:
            self.nonce = random.randbytes(8)
        else:
            self.nonce = nonce

    @property
    def message_type(self) -> bytes:
        return b'ping'.ljust(12, b'\0')

    @property
    def payload(self) -> bytes:
        return self.nonce

    @classmethod
    def from_bytes(cls, data: bytes) -> Ping:
        return cls(data)


class Pong(Message):
    def __init__(self, nonce: bytes = None):
        if nonce is None:
            self.nonce = random.randbytes(8)
        else:
            self.nonce = nonce

    @property
    def message_type(self) -> bytes:
        return b'pong'.ljust(12, b'\0')

    @property
    def payload(self) -> bytes:
        return self.nonce

    @classmethod
    def from_bytes(cls, data: bytes) -> Message:
        return cls(data)


class HeaderOnly(Message, ABC):
    @property
    @abstractmethod
    def message_type(self) -> bytes:
        return NotImplemented

    @property
    def payload(self) -> bytes:
        return b''

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls()


class VerAck(HeaderOnly):
    @property
    def message_type(self) -> bytes:
        return b'verack'.ljust(12, b'\0')


class Addr(Message):
    def __init__(self, addresses: list[NetworkAddress]):
        self.addresses = addresses

    @property
    def count(self) -> int:
        return len(self.addresses)

    @property
    def message_type(self) -> bytes:
        return b'addr'.ljust(12, b'\0')

    @property
    def payload(self) -> bytes:
        return bytes(VarInt(self.count)) \
               + b''.join(bytes(adr) for adr in self.addresses)

    @classmethod
    def from_bytes(cls, data: bytes) -> Message:
        count_len = VarInt.get_length(data[0])
        count = int(VarInt(data[:count_len]))
        addresses = [NetworkAddress.from_bytes(data[count_len + x * 22: count_len + x * 22 + 22]) for x in range(count)]

        return cls(addresses)


class GetAddr(HeaderOnly):
    @property
    def message_type(self) -> bytes:
        return b'getaddr'.ljust(12, b'\0')


class Reject(Message):
    pass


message_types = {b'version': Version,
                 b'verack': VerAck,
                 b'ping': Ping,
                 b'pong': Pong,
                 b'addr': Addr,
                 b'getaddr': GetAddr,
                 b'reject': Reject}


if __name__ == '__main__':
    addr1 = NetworkAddress(b'\x0a\x01\xa8\x04', 500)
    addr2 = NetworkAddress(b'\255\255\255\255', 5000)
    v = Version(1231, addr1, addr2)
    l = Addr([addr1, addr2])
    l2 = Message.from_bytes(bytes(l))
