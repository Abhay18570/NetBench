"""UDP wire format: bounded JSON controls and individually numbered DATA.

DATA = b'NBD1' + 16-byte UUID + uint32 sequence (network order) + payload.
1,200 payload bytes + 24 header bytes + 28 IPv4/UDP bytes = 1,252 bytes,
keeping packets below a typical 1,500-byte MTU (smaller paths may fragment).
"""

import json
import struct
import uuid
from typing import Any

from .protocol import MAX_SIZE_MB, MIB, ProtocolError

PAYLOAD_SIZE = 1200
DATA_HEADER = struct.Struct('!4s16sI')
CONTROL_MAGIC = b'NBC1'
MAX_CONTROL_SIZE = 1024
MAX_DATAGRAM_SIZE = DATA_HEADER.size + PAYLOAD_SIZE
CONTROL_TIMEOUT = 0.75
CONTROL_ATTEMPTS = 4
END_GRACE_SECONDS = 0.15
SESSION_IDLE_SECONDS = 30.0
SESSION_MAX_SECONDS = 120.0
MAX_SESSIONS = 16


def session_id(value: Any) -> str:
    """Require canonical UUID hex to avoid alternate identifiers for a session."""
    if not isinstance(value, str) or len(value) != 32:
        raise ProtocolError('Invalid session ID')
    try:
        if uuid.UUID(hex=value).hex != value:
            raise ValueError('Noncanonical UUID')
    except ValueError as exc:
        raise ProtocolError('Invalid session ID') from exc
    return value


def encode_control(kind: str, test_id: str, **fields: Any) -> bytes:
    """Encode a bounded control datagram."""
    data = CONTROL_MAGIC + json.dumps({'type': kind, 'id': test_id, **fields}, allow_nan=False).encode()
    if len(data) > MAX_CONTROL_SIZE:
        raise ProtocolError('Control datagram too large')
    return data


def decode_control(data: bytes) -> dict[str, Any]:
    """Reject malformed, oversized or structurally invalid controls."""
    if not data.startswith(CONTROL_MAGIC) or len(data) > MAX_CONTROL_SIZE:
        raise ProtocolError('Invalid control datagram')
    try:
        message = json.loads(data[len(CONTROL_MAGIC):])
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ProtocolError('Invalid control JSON') from exc
    if not isinstance(message, dict) or not isinstance(message.get('type'), str):
        raise ProtocolError('Invalid control object')
    session_id(message.get('id'))
    return message


def validate_metadata(message: dict[str, Any]) -> tuple[int, int]:
    """Bound byte and packet counts before allocating the sequence bitmap."""
    count, packets = message.get('bytes'), message.get('packets')
    if type(count) is not int or not 1 <= count <= MAX_SIZE_MB * MIB:
        raise ProtocolError('Invalid expected byte count')
    if type(packets) is not int or packets != (count + PAYLOAD_SIZE - 1) // PAYLOAD_SIZE:
        raise ProtocolError('Invalid expected packet count')
    if type(message.get('payload_size')) is not int or message['payload_size'] != PAYLOAD_SIZE:
        raise ProtocolError('Unsupported payload size')
    return count, packets


def encode_data(test_id: str, sequence: int, payload: bytes) -> bytes:
    """Encode one DATA packet; no DATA retransmission is performed."""
    if not 0 < len(payload) <= PAYLOAD_SIZE:
        raise ProtocolError('Invalid DATA payload size')
    return DATA_HEADER.pack(b'NBD1', bytes.fromhex(test_id), sequence) + payload


def decode_data(data: bytes) -> tuple[str, int, bytes]:
    """Decode a bounded binary datagram."""
    if not DATA_HEADER.size < len(data) <= MAX_DATAGRAM_SIZE:
        raise ProtocolError('Invalid DATA size')
    magic, identifier, sequence = DATA_HEADER.unpack_from(data)
    if magic != b'NBD1':
        raise ProtocolError('Invalid DATA marker')
    return identifier.hex(), sequence, data[DATA_HEADER.size:]
