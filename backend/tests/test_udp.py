"""UDP unit and real localhost integration tests (requires local socket access)."""

import contextlib
import io
import socket
import threading
import unittest
import uuid
from unittest.mock import patch

from backend.metrics.calculator import calculate_udp_metrics, udp_packet_loss
from backend.network.protocol import ProtocolError, MIB
from backend.network.udp_client import exchange, run_test
from backend.network.udp_protocol import (
    PAYLOAD_SIZE, END_GRACE_SECONDS, SESSION_IDLE_SECONDS, MAX_SESSIONS,
    encode_control, decode_control, encode_data,
)
from backend.network.udp_server import UDPReceiver, serve_socket


class UDPTests(unittest.TestCase):
    def setUp(self):
        self.receiver = UDPReceiver()
        self.identifier = uuid.uuid4().hex
        self.peer = ('127.0.0.1', 12345)
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def start(self, size=2500):
        return self.receiver.handle(encode_control('START', self.identifier, bytes=size,
            packets=(size + PAYLOAD_SIZE - 1) // PAYLOAD_SIZE,
            payload_size=PAYLOAD_SIZE), self.peer, 1.0)

    def test_udp_metrics_and_loss(self):
        result = calculate_udp_metrics('localhost:5002', 1, 1000, 900, 10, 9, 1, 1.5, 2, 2.001)
        self.assertEqual(result['packets_lost'], 1)
        self.assertEqual(result['packet_loss_percent'], 10)
        self.assertAlmostEqual(result['throughput_mbps'], 0.0144)
        self.assertAlmostEqual(result['application_rtt_ms'], 1)
        self.assertEqual(udp_packet_loss(10, 0), (10, 100))
        self.assertEqual(udp_packet_loss(10, 10), (0, 0))
        for sent, received in [(0, 0), (10, 11), (10, -1), (True, 1)]:
            with self.assertRaises(ValueError):
                udp_packet_loss(sent, received)

    def test_duplicates_reordering_and_short_final_packet(self):
        self.start()
        # Sequence 1 is genuinely absent in this deterministic protocol test.
        for sequence, length in [(2, 100), (0, 1200), (0, 1200)]:
            self.receiver.handle(encode_data(self.identifier, sequence, b'x' * length), self.peer, 1.1)
        session = self.receiver.sessions[self.identifier]
        self.assertEqual(session.received_bytes, 1300)
        self.assertEqual(session.received_packets, 2)
        self.assertEqual(udp_packet_loss(session.expected_packets, session.received_packets)[0], 1)

    def test_end_retries_cached_result_and_late_data(self):
        self.start()
        end = encode_control('END', self.identifier)
        self.assertIsNone(self.receiver.handle(end, self.peer, 2))
        self.receiver.handle(end, self.peer, 2.05)
        self.assertEqual(self.receiver.sessions[self.identifier].end_deadline, 2 + END_GRACE_SECONDS)
        self.receiver.handle(encode_data(self.identifier, 2, b'x' * 100), self.peer, 2.1)
        replies = self.receiver.maintain(2.2)
        result = replies[0][0]
        self.assertEqual(decode_control(result)['bytes_received'], 100)
        self.receiver.handle(encode_data(self.identifier, 0, b'x' * 1200), self.peer, 2.3)
        self.assertEqual(self.receiver.handle(end, self.peer, 2.4), result)

    def test_start_retry_does_not_reset_counts_and_peer_isolation(self):
        ready = self.start()
        packet = encode_data(self.identifier, 0, b'x' * 1200)
        self.receiver.handle(packet, self.peer, 1.1)
        self.assertEqual(self.start(), ready)
        self.assertEqual(self.receiver.sessions[self.identifier].received_packets, 1)
        self.receiver.handle(encode_data(self.identifier, 1, b'x' * 1200), ('127.0.0.1', 9999), 1.2)
        self.assertEqual(self.receiver.sessions[self.identifier].received_packets, 1)
        with self.assertRaises(ProtocolError):
            self.receiver.handle(encode_control('END', self.identifier), ('127.0.0.1', 9999), 2)

    def test_malformed_controls_and_data(self):
        for data in (b'garbage', b'NBC1[]', b'NBC1{', b'NBC1' + b'x' * 1024,
                     encode_control('START', self.identifier, bytes=True, packets=1, payload_size=1200),
                     encode_control('START', self.identifier, bytes=2**50, packets=1, payload_size=1200),
                     encode_control('START', self.identifier, bytes=1200, packets=2, payload_size=1200),
                     encode_control('UNKNOWN', self.identifier)):
            with self.subTest(data=data[:30]), self.assertRaises(ProtocolError):
                self.receiver.handle(data, self.peer, 1)
        self.start()
        for sequence, payload in [(3, b'x'), (0, b'x'), (2, b'x' * 1200)]:
            with self.assertRaises(ProtocolError):
                self.receiver.handle(encode_data(self.identifier, sequence, payload), self.peer, 1.1)

    def test_session_limit_and_expiration(self):
        for _ in range(MAX_SESSIONS):
            self.identifier = uuid.uuid4().hex
            self.start()
        self.identifier = uuid.uuid4().hex
        self.assertEqual(decode_control(self.start())['type'], 'ERROR')
        self.receiver.maintain(2 + SESSION_IDLE_SECONDS)
        self.assertEqual(len(self.receiver.sessions), 0)
        self.assertEqual(decode_control(self.start())['type'], 'READY')

    def test_controls_retry_and_eventually_timeout(self):
        class LossySocket:
            def __init__(self, always_drop=False):
                self.requests = []
                self.always_drop = always_drop

            def send(self, data):
                self.requests.append(decode_control(data))

            def settimeout(self, value):
                pass

            def recv(self, count):
                if len(self.requests) == 1 or self.always_drop:
                    raise socket.timeout()
                request = self.requests[-1]
                return encode_control('PONG', request['id'], nonce=request['nonce'])

        sock = LossySocket()
        reply, _, _ = exchange(sock, 'PING', 'PONG', self.identifier)
        self.assertEqual(reply['type'], 'PONG')
        self.assertEqual(len(sock.requests), 2)
        self.assertNotEqual(sock.requests[0]['nonce'], sock.requests[1]['nonce'])
        with patch('backend.network.udp_client.CONTROL_ATTEMPTS', 2):
            with self.assertRaises(TimeoutError):
                exchange(LossySocket(True), 'PING', 'PONG', self.identifier)


class UDPLocalhostTests(unittest.TestCase):
    def test_one_mb_and_sequential_tests_on_same_server(self):
        stop = threading.Event()
        failures = []
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]

            def worker():
                try:
                    serve_socket(sock, stop)
                except Exception as exc:
                    failures.append(exc)

            thread = threading.Thread(target=worker, daemon=True)
            thread.start()
            try:
                # A malformed datagram must not terminate the real receiver.
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
                    sender.sendto(b'bad metadata', ('127.0.0.1', port))
                for _ in range(2):
                    result = run_test('127.0.0.1', port, 1)
                    self.assertEqual(result['bytes_sent'], MIB)
                    self.assertEqual(result['packets_sent'], 874)
                    self.assertGreater(result['bytes_received'], 0)
                    self.assertLessEqual(result['bytes_received'], MIB)
                    self.assertEqual(result['packets_lost'], 874 - result['packets_received'])
                    self.assertAlmostEqual(result['packet_loss_percent'], result['packets_lost'] / 874 * 100)
                    self.assertGreater(result['application_rtt_ms'], 0)
                    self.assertGreater(result['transfer_time_seconds'], 0)
                    self.assertAlmostEqual(result['throughput_mbps'], result['bytes_received'] * 8 / result['transfer_time_seconds'] / 1_000_000)
                    self.assertTrue(thread.is_alive())
            finally:
                stop.set()
                thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
            self.assertEqual(failures, [])


if __name__ == '__main__':
    unittest.main()
