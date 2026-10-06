"""Dependency-light regression checks: python -m unittest discover -s backend/tests."""

import json
import struct
import unittest

from backend.app import app
from backend.metrics.calculator import calculate_metrics, throughput_mbps
from backend.network.protocol import ProtocolError, receive_message, recv_exact, valid_size
import argparse


class FragmentedSocket:
    """A stream delivering at most two bytes per read, regardless of framing."""

    def __init__(self, data: bytes):
        self.data = data

    def recv(self, count: int) -> bytes:
        chunk = self.data[:min(count, 2)]
        self.data = self.data[len(chunk):]
        return chunk


def frame(value: object) -> bytes:
    data = json.dumps(value).encode()
    return struct.pack('!I', len(data)) + data


class BackendTests(unittest.TestCase):
    def test_fragmented_and_coalesced_frames_preserve_payload(self):
        stream = FragmentedSocket(frame({'type': 'PING'}) + frame({'type': 'PONG'}) + b'payload')
        self.assertEqual(receive_message(stream), {'type': 'PING'})
        self.assertEqual(receive_message(stream), {'type': 'PONG'})
        self.assertEqual(recv_exact(stream, 7), b'payload')

    def test_truncated_frame(self):
        with self.assertRaises(ConnectionError):
            receive_message(FragmentedSocket(struct.pack('!I', 10) + b'{}'))

    def test_invalid_control_messages(self):
        for data in (struct.pack('!I', 0), struct.pack('!I', 4097), frame([]), struct.pack('!I', 1) + b'x'):
            with self.subTest(data=data), self.assertRaises(ProtocolError):
                receive_message(FragmentedSocket(data))

    def test_metric_units_and_packet_loss(self):
        result = calculate_metrics(1_000_000, 1.0, 1.5, 2.0, 2.002)
        self.assertEqual(result['bytes_transferred'], 1_000_000)
        self.assertEqual(result['transfer_time_seconds'], 0.5)
        self.assertEqual(result['throughput_mbps'], 16)
        self.assertAlmostEqual(result['application_rtt_ms'], 2)
        self.assertIsNone(result['packet_loss_percent'])

    def test_invalid_duration_and_sizes(self):
        for duration in (0, -1, float('nan'), float('inf')):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                throughput_mbps(100, duration)
        for size in ('0', '-1', '1025', '1.5', 'bad'):
            with self.subTest(size=size), self.assertRaises(argparse.ArgumentTypeError):
                valid_size(size)
        for size in (1, 5, 10, 25, 50):
            self.assertEqual(valid_size(str(size)), size)

    def test_health_and_local_cors(self):
        client = app.test_client()
        response = client.get('/api/health', headers={'Origin': 'http://localhost:5173'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {'status': 'ok', 'service': 'NetBench API'})
        self.assertEqual(response.headers['Access-Control-Allow-Origin'], 'http://localhost:5173')
        remote = client.get('/api/health', headers={'Origin': 'https://example.com'})
        self.assertNotIn('Access-Control-Allow-Origin', remote.headers)
        self.assertEqual(client.post('/api/health').status_code, 405)


if __name__ == '__main__':
    unittest.main()
