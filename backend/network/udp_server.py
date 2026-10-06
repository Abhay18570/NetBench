"""Bounded-session UDP receiver supporting sequential tests and control retries."""

import argparse
from dataclasses import dataclass, field
import socket
import sys
import time
from threading import Event

from backend.metrics.calculator import udp_packet_loss
from .protocol import ProtocolError, valid_port
from .udp_protocol import (
    PAYLOAD_SIZE, MAX_DATAGRAM_SIZE, MAX_SESSIONS, END_GRACE_SECONDS,
    SESSION_IDLE_SECONDS, SESSION_MAX_SECONDS, decode_control, decode_data,
    encode_control, validate_metadata,
)


@dataclass
class Session:
    """Bounded sequence bitmap; duplicate DATA never increases counters."""

    test_id: str
    peer: tuple[str, int]
    expected_bytes: int
    expected_packets: int
    created: float
    updated: float
    seen: bytearray = field(init=False)
    received_bytes: int = 0
    received_packets: int = 0
    end_deadline: float | None = None
    result: bytes | None = None

    def __post_init__(self) -> None:
        # Metadata is validated first. At most ~112 KiB per 1-GiB session.
        self.seen = bytearray((self.expected_packets + 7) // 8)

    def receive(self, sequence: int, payload: bytes, now: float) -> None:
        """Count each valid sequence once, including a shorter final payload."""
        if self.result is not None:
            return
        if not 0 <= sequence < self.expected_packets:
            raise ProtocolError('DATA sequence outside expected range')
        expected = min(PAYLOAD_SIZE, self.expected_bytes - sequence * PAYLOAD_SIZE)
        if len(payload) != expected:
            raise ProtocolError('DATA payload does not match expected sequence size')
        index, bit = divmod(sequence, 8)
        if not self.seen[index] & (1 << bit):
            self.seen[index] |= 1 << bit
            self.received_packets += 1
            self.received_bytes += len(payload)
        self.updated = now


class UDPReceiver:
    """Protocol state independent of socket I/O for deterministic validation."""

    def __init__(self) -> None:
        self.sessions: dict[str, Session] = {}

    def maintain(self, now: float) -> list[tuple[bytes, tuple[str, int]]]:
        """Finalize END after a fixed reorder window, and expire stale sessions."""
        replies = []
        for test_id, session in list(self.sessions.items()):
            if session.result is None and session.end_deadline is not None and now >= session.end_deadline:
                lost, loss = udp_packet_loss(session.expected_packets, session.received_packets)
                session.result = encode_control('RESULT', test_id,
                    bytes_received=session.received_bytes, packets_received=session.received_packets)
                session.updated = now
                replies.append((session.result, session.peer))
                print(f'Transfer completed: {test_id}\nBytes received: {session.received_bytes}\n'
                      f'Packets received: {session.received_packets}\nPackets lost: {lost}\n'
                      f'Packet loss: {loss:.2f}%', flush=True)
            if now - session.updated >= SESSION_IDLE_SECONDS or now - session.created >= SESSION_MAX_SECONDS:
                del self.sessions[test_id]
        return replies

    def handle(self, data: bytes, peer: tuple[str, int], now: float) -> bytes | None:
        """Process a datagram; reject malformed or cross-peer session traffic."""
        if data.startswith(b'NBD1'):
            test_id, sequence, payload = decode_data(data)
            session = self.sessions.get(test_id)
            if session is not None and session.peer == peer:
                session.receive(sequence, payload, now)
            return None
        message = decode_control(data)
        test_id, kind = message['id'], message['type']
        if kind == 'PING':
            nonce = message.get('nonce')
            if not isinstance(nonce, str) or len(nonce) != 32:
                raise ProtocolError('Invalid PING nonce')
            return encode_control('PONG', test_id, nonce=nonce)
        session = self.sessions.get(test_id)
        if session is not None and session.peer != peer:
            raise ProtocolError('Session belongs to another endpoint')
        if kind == 'START':
            count, packets = validate_metadata(message)
            if session is None:
                if len(self.sessions) >= MAX_SESSIONS:
                    return encode_control('ERROR', test_id, error='Server session limit reached')
                session = Session(test_id, peer, count, packets, now, now)
                self.sessions[test_id] = session
                print(f'\nNew test: {test_id}\nExpected bytes: {count}\nExpected packets: {packets}', flush=True)
            elif (session.expected_bytes, session.expected_packets) != (count, packets) or session.end_deadline is not None:
                raise ProtocolError('Conflicting or already ended START')
            session.updated = now
            return encode_control('READY', test_id, bytes=count, packets=packets)
        if kind == 'END':
            if session is None:
                return encode_control('ERROR', test_id, error='Unknown or expired session')
            if session.result is not None:
                return session.result
            # END retries do not extend the window indefinitely.
            if session.end_deadline is None:
                session.end_deadline = now + END_GRACE_SECONDS
            session.updated = now
            return None
        raise ProtocolError('Unsupported control type')


def serve_socket(sock: socket.socket, stop: Event | None = None) -> None:
    """Serve using an already-bound socket; optional stop supports live tests."""
    receiver = UDPReceiver()
    sock.settimeout(0.02)
    while stop is None or not stop.is_set():
        for reply, peer in receiver.maintain(time.perf_counter()):
            try:
                sock.sendto(reply, peer)
            except OSError as exc:
                print(f'UDP reply failed: {exc}', flush=True)
        try:
            # One extra byte detects oversize/truncated datagrams safely.
            data, peer = sock.recvfrom(MAX_DATAGRAM_SIZE + 1)
            reply = receiver.handle(data, peer, time.perf_counter())
            if reply is not None:
                sock.sendto(reply, peer)
        except socket.timeout:
            continue
        except ProtocolError:
            # Malformed datagrams are dropped without amplification or log spam.
            continue
        except OSError as exc:
            print(f'UDP socket error: {exc}', flush=True)


def serve(host: str = '0.0.0.0', port: int = 5002) -> None:
    """Bind an IPv4 datagram socket and remain available for sequential tests."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((host, port))
        print(f'NetBench UDP Server\nListening on {host}:{port}', flush=True)
        serve_socket(sock)


def main() -> int:
    """Launch the UDP server from the project root."""
    parser = argparse.ArgumentParser(description='NetBench UDP receiver')
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=valid_port, default=5002)
    args = parser.parse_args()
    try:
        serve(args.host, args.port)
    except KeyboardInterrupt:
        print('\nUDP server stopped.', flush=True)
    except OSError as exc:
        print(f'UDP server error: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
