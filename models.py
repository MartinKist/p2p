#!/usr/bin/env python3
# (c) 2021 Martin Kistler

from __future__ import annotations

import random
import time
from abc import ABC, abstractmethod
from hashlib import sha256
from typing import Union


BYTEORDER = 'little'


class MessageError(Exception):
    def __init__(self, msg_type: bytes, length: int, checksum: bytes, payload: bytes):
        self.msg_type = msg_type
        self.length = length
        self.checksum = checksum
        self.payload = payload

        # TODO: add description parameter


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
        """
        Returns the number of bytes this VarInt has, including prefix, if existent.
        """
        return len(bytes(self))

    @staticmethod
    def get_length(first_byte: int) -> int:
        """
        Returns the expected length of the VarInt, by examining the first byte.
        """
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


class NetworkAddress(StructABC):
    def __init__(self, address: Union[bytes, str], port: int, timestamp: int = None):
        self.address = address
        self.port = port

        if timestamp is None:
            self.timestamp = int(time.time())
        else:
            self.timestamp = timestamp

        if isinstance(address, bytes):
            self.address = ".".join(str(val) for val in self.address)
        else:
            self.address = self.address.strip()

    @property
    def addr_bytes(self):
        values = self.address.split('.')
        return bytes(map(int, values))

    def __bytes__(self) -> bytes:
        return self.timestamp.to_bytes(4, BYTEORDER) \
               + self.addr_bytes \
               + self.port.to_bytes(2, BYTEORDER)

    @classmethod
    def from_bytes(cls, data: bytes) -> NetworkAddress:
        timestamp = int.from_bytes(data[:4], BYTEORDER)
        address = data[4:8]
        port = int.from_bytes(data[8:10], BYTEORDER)

        return cls(address, port, timestamp)

    def __str__(self):
        return self.address + ':' + str(self.port)


class Message(StructABC, ABC):
    # TODO: write down specification
    # https://en.bitcoin.it/wiki/Protocol_documentation#Common_structures

    @staticmethod
    def calculate_checksum(data: bytes) -> bytes:
        return sha256(sha256(data).digest()).digest()[:4]

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
        return self.calculate_checksum(self.payload)

    @property
    def length(self) -> int:
        return len(self.payload)

    def __bytes__(self) -> bytes:
        nonce = random.randbytes(4)     # 4 Byte nonce to identify identical messages
        return self.message_type \
               + self.length.to_bytes(4, BYTEORDER) \
               + self.checksum \
               + nonce \
               + self.payload

    @classmethod
    @abstractmethod
    def from_bytes(cls, data: bytes) -> Message:
        msg_type = data[:12].rstrip(b'\0')
        length = int.from_bytes(data[12:16], BYTEORDER)
        checksum = data[16:20]
        nonce = data[20:24]
        payload = data[24:24 + length]

        if cls.calculate_checksum(payload) == checksum and msg_type in message_types:
            return message_types[msg_type].from_bytes(payload)
        else:
            raise MessageError(msg_type, length, checksum, payload)

    def __str__(self):
        return f'Message type: {self.message_type}\n' \
               + f'Payload length: {len(self.payload)}\n' \
               + f'Checksum: {self.checksum}\n' \
               + 'Payload:\n' \
               + str(self.payload)


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


class Version(Message):
    def __init__(self, version: int, addr_recv: NetworkAddress, addr_from: NetworkAddress, nonce: bytes, timestamp: int = None):
        self.version = version
        self.addr_recv = addr_recv
        self.addr_from = addr_from
        self.nonce = nonce

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
               + bytes(self.addr_from) \
               + self.nonce

    @classmethod
    def from_bytes(cls, data: bytes) -> Version:
        version = int.from_bytes(data[:4], BYTEORDER)
        timestamp = int.from_bytes(data[4:12], BYTEORDER)
        addr_recv = NetworkAddress.from_bytes(data[12:22])
        addr_from = NetworkAddress.from_bytes(data[22:32])
        nonce = data[32:40]

        return cls(version, addr_recv, addr_from, nonce, timestamp=timestamp)


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


class Reject(Message):
    # TODO
    @property
    def message_type(self) -> bytes:
        return b'reject'.ljust(12, b'\0')

    @property
    def payload(self) -> bytes:
        pass

    @classmethod
    def from_bytes(cls, data: bytes) -> Message:
        pass


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
        addresses = [NetworkAddress.from_bytes(data[count_len + x * 10: count_len + x * 10 + 10]) for x in range(count)]

        return cls(addresses)


class VerAck(HeaderOnly):
    @property
    def message_type(self) -> bytes:
        return b'verack'.ljust(12, b'\0')


class GetAddr(HeaderOnly):
    @property
    def message_type(self) -> bytes:
        return b'getaddr'.ljust(12, b'\0')


class ChatMessage(Message):
    def __init__(self, chat_message: Union[bytes, str]):
        if isinstance(chat_message, bytes):
            self.chat_message = chat_message.decode('utf-8')
        else:
            self.chat_message = chat_message

    @property
    def message_type(self) -> bytes:
        return b'chat'.ljust(12, b'\0')

    @property
    def payload(self) -> bytes:
        return self.chat_message.encode('utf-8')

    @classmethod
    def from_bytes(cls, data: bytes) -> Message:
        return cls(data)


message_types = {b'version': Version,
                 b'verack': VerAck,
                 b'ping': Ping,
                 b'pong': Pong,
                 b'addr': Addr,
                 b'getaddr': GetAddr,
                 b'reject': Reject,
                 b'chat': ChatMessage}
