"""HTTP contract tests; engine mocks leave the existing live socket tests intact."""

import socket
import unittest
from unittest.mock import patch

from backend.app import app, _test_lock
from backend.network.protocol import ProtocolError

TCP = {'bytes_transferred': 1048576, 'transfer_time_seconds': 0.012345,
       'throughput_mbps': 679.5146213041717, 'application_rtt_ms': 0.13,
       'packet_loss_percent': None}
UDP = {'protocol': 'UDP', 'server': '127.0.0.1:5002', 'test_size_mb': 1,
       'bytes_sent': 1048576, 'bytes_received': 1047376, 'packets_sent': 874,
       'packets_received': 873, 'packets_lost': 1, 'packet_loss_percent': 100 / 874,
       'transfer_time_seconds': 0.2, 'throughput_mbps': 41.89504, 'application_rtt_ms': 0.2}


class APITests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.payload = {'host': '127.0.0.1', 'size_mb': 1}

    def test_health(self):
        response = self.client.get('/api/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {'status': 'ok', 'service': 'NetBench API'})

    @patch('backend.app.run_tcp_test')
    def test_invalid_sizes_never_invoke_network(self, engine):
        for size in (0, 2, 100, -1, True, '1', 1.0, None):
            with self.subTest(size=size):
                response = self.client.post('/api/test/tcp', json={**self.payload, 'size_mb': size})
                self.assertEqual(response.status_code, 400)
                self.assertIn('error', response.json)
        engine.assert_not_called()

    def test_malformed_requests(self):
        for path in ('tcp', 'udp', 'compare'):
            for body in ('{', 'null', '[]', '{}'):
                response = self.client.post(f'/api/test/{path}', data=body, content_type='application/json')
                self.assertEqual(response.status_code, 400)
                self.assertIn('error', response.json)
        self.assertEqual(self.client.post('/api/test/tcp', data='x').status_code, 400)
        oversized = self.client.post('/api/test/tcp', data='x' * 4097, content_type='application/json')
        self.assertEqual(oversized.status_code, 413)
        self.assertIn('error', oversized.json)

    def test_invalid_hosts(self):
        for host in ('', ' ', None, 123, 'http://localhost', 'localhost:5001', 'bad\x00host', 'a b'):
            response = self.client.post('/api/test/tcp', json={**self.payload, 'host': host})
            self.assertEqual(response.status_code, 400)

    @patch('backend.app.run_tcp_test', return_value=TCP)
    def test_tcp_mapping_and_supported_sizes(self, engine):
        for size in (1, 5, 10, 25, 50):
            response = self.client.post('/api/test/tcp', json={**self.payload, 'size_mb': size})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json, {**TCP, 'protocol': 'TCP', 'host': '127.0.0.1', 'port': 5001, 'test_size_mb': size})
            engine.assert_called_with(host='127.0.0.1', port=5001, size_mb=size)

    @patch('backend.app.run_udp_test', return_value=UDP)
    def test_udp_mapping(self, engine):
        response = self.client.post('/api/test/udp', json=self.payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {**UDP, 'host': '127.0.0.1', 'port': 5002})
        engine.assert_called_once_with(host='127.0.0.1', port=5002, size_mb=1)

    def test_compare_mapping_and_order(self):
        order = []
        def tcp(**kwargs):
            order.append(('tcp', kwargs))
            return TCP
        def udp(**kwargs):
            order.append(('udp', kwargs))
            return UDP
        with patch('backend.app.run_tcp_test', side_effect=tcp), patch('backend.app.run_udp_test', side_effect=udp):
            response = self.client.post('/api/test/compare', json=self.payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item[0] for item in order], ['tcp', 'udp'])
        self.assertEqual(order[0][1], {'host': '127.0.0.1', 'port': 5001, 'size_mb': 1})
        self.assertEqual(order[1][1], {'host': '127.0.0.1', 'port': 5002, 'size_mb': 1})
        self.assertEqual(response.json['tcp']['throughput_mbps'], TCP['throughput_mbps'])
        self.assertEqual(response.json['udp']['bytes_received'], UDP['bytes_received'])

    def test_error_mapping_and_lock_release(self):
        for error, status in [(ConnectionRefusedError('refused'), 503), (TimeoutError('timeout'), 504),
                              (socket.gaierror('unknown host'), 400), (OSError('socket failed'), 502),
                              (ProtocolError('bad result'), 502)]:
            with self.subTest(error=error), patch('backend.app.run_tcp_test', side_effect=error):
                response = self.client.post('/api/test/tcp', json=self.payload)
                self.assertEqual(response.status_code, status)
                self.assertIn('error', response.json)
                self.assertEqual(response.json['failed_protocol'], 'TCP')
                self.assertFalse(_test_lock.locked())

    @patch('backend.app.run_tcp_test', return_value=TCP)
    @patch('backend.app.run_udp_test', side_effect=TimeoutError('UDP unavailable'))
    def test_partial_compare_is_error(self, udp, tcp):
        response = self.client.post('/api/test/compare', json=self.payload)
        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.json['completed_protocols'], ['TCP'])
        self.assertEqual(response.json['failed_protocol'], 'UDP')
        self.assertNotIn('tcp', response.json)
        tcp.assert_called_once()
        udp.assert_called_once()

    @patch('backend.app.run_tcp_test', side_effect=ConnectionRefusedError('TCP unavailable'))
    @patch('backend.app.run_udp_test')
    def test_compare_stops_on_first_failure(self, udp, tcp):
        response = self.client.post('/api/test/compare', json=self.payload)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json['completed_protocols'], [])
        udp.assert_not_called()

    def test_busy_api(self):
        _test_lock.acquire()
        try:
            response = self.client.post('/api/test/compare', json=self.payload)
            self.assertEqual(response.status_code, 409)
            self.assertIn('error', response.json)
        finally:
            _test_lock.release()

    @patch('backend.app.run_tcp_test', return_value=TCP)
    def test_local_cors_on_post_and_preflight(self, engine):
        origin = {'Origin': 'http://localhost:5173'}
        response = self.client.post('/api/test/tcp', json=self.payload, headers=origin)
        self.assertEqual(response.headers['Access-Control-Allow-Origin'], origin['Origin'])
        response = self.client.options('/api/test/compare', headers={**origin,
            'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'content-type'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('POST', response.headers['Access-Control-Allow-Methods'])


if __name__ == '__main__':
    unittest.main()
