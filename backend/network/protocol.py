"""Shared framing and limits for the NetBench TCP wire protocol."""

import argparse
import json
import socket
import struct
from typing import Any

MIB = 1024 * 1024
MAX_SIZE_MB = 1024
MAX_CONTROL_BYTES = 4096
CHUNK_SIZE = 64 * 1024
SOCKET_TIMEOUT = 30.0


class ProtocolError(ValueError):
    """A peer sent an invalid or unexpected protocol message."""


def recv_exact(connection: socket.socket, count: int) -> bytes:
    """Read exactly count bytes, without consuming any following frame/payload."""
    data = bytearray()
    while len(data) < count:
        chunk = connection.recv(count - len(data))
        if not chunk:
            raise ConnectionError(f"Peer disconnected with {count - len(data)} bytes pending")
        data.extend(chunk)
    return bytes(data)


def send_message(connection: socket.socket, message: dict[str, Any]) -> None:
    """Send a JSON object preceded by its four-byte network-order length."""
    encoded = json.dumps(message, allow_nan=False).encode('utf-8')
    if not 0 < len(encoded) <= MAX_CONTROL_BYTES:
        raise ProtocolError('Control message exceeds size limit')
    connection.sendall(struct.pack('!I', len(encoded)) + encoded)


def receive_message(connection: socket.socket) -> dict[str, Any]:
    """Read a bounded JSON frame, handling split/coalesced TCP reads."""
    length = struct.unpack('!I', recv_exact(connection, 4))[0]
    if not 0 < length <= MAX_CONTROL_BYTES:
        raise ProtocolError('Invalid control message length')
    try:
        message = json.loads(recv_exact(connection, length).decode('utf-8'))
    except (UnicodeError, ValueError) as exc:
        raise ProtocolError('Invalid JSON control message') from exc
    if not isinstance(message, dict):
        raise ProtocolError('Control message must be an object')
    return message


def expect_message(connection: socket.socket, expected_type: str) -> dict[str, Any]:
    """Receive a frame and verify the expected protocol stage."""
    message = receive_message(connection)
    if message.get('type') != expected_type:
        raise ProtocolError(f"Expected {expected_type}, received {message.get('type')!r}")
    return message


def valid_port(value: str) -> int:
    """Validate a command-line TCP port."""
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError('Port must be an integer') from exc
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError('Port must be between 1 and 65535')
    return port


def valid_size(value: str) -> int:
    """Validate a whole-MB test size, capped at 1 GiB."""
    try:
        size = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError('Size must be a whole number of MB') from exc
    if not 1 <= size <= MAX_SIZE_MB:
        raise argparse.ArgumentTypeError(f'Size must be between 1 and {MAX_SIZE_MB} MB')
    return size
