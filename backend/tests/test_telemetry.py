"""Real SDK aggregation tests without Collector or exporter network access."""

import copy
import threading
import unittest
from unittest.mock import patch

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader, MetricExporter, MetricExportResult, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource

from backend.app import app
from backend.telemetry import metrics as telemetry
from backend.tests.test_api import TCP, UDP


class TelemetryTests(unittest.TestCase):
    def setUp(self):
        self.reader = InMemoryMetricReader()
        self.provider = MeterProvider(metric_readers=[self.reader], resource=Resource(telemetry.RESOURCE_ATTRIBUTES), shutdown_on_exit=False)
        self.recorder = telemetry.NetworkMetrics(self.provider)
        self.addCleanup(self.provider.shutdown)
        patcher = patch.object(telemetry, '_recorder', self.recorder)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = app.test_client()

    def points(self):
        data = self.reader.get_metrics_data()
        if data is None:
            return {}
        return {metric.name.removeprefix('netbench.network.'): list(metric.data.data_points)
                for resource in data.resource_metrics for scope in resource.scope_metrics for metric in scope.metrics}

    def test_tcp_success_values_and_no_packet_metrics(self):
        result = {**TCP, 'protocol': 'TCP', 'host': 'private-host'}
        before = copy.deepcopy(result)
        telemetry.record_network_test(result)
        points = self.points()
        self.assertEqual(points['tests'][0].value, 1)
        self.assertEqual(dict(points['tests'][0].attributes), {'protocol': 'tcp', 'status': 'success'})
        for name, field in [('throughput', 'throughput_mbps'), ('transfer.duration', 'transfer_time_seconds'), ('rtt', 'application_rtt_ms')]:
            self.assertEqual(points[name][0].sum, TCP[field])
            self.assertEqual(points[name][0].count, 1)
        for name in ['bytes.sent', 'bytes.received']:
            self.assertEqual(points[name][0].value, TCP['bytes_transferred'])
        self.assertFalse(any(name.startswith('packet') for name in points))
        self.assertEqual(result, before)

    def test_udp_success_all_values_and_attributes(self):
        before = copy.deepcopy(UDP)
        telemetry.record_network_test(UDP)
        points = self.points()
        for name, field in [('bytes.sent', 'bytes_sent'), ('bytes.received', 'bytes_received'),
                            ('packets.sent', 'packets_sent'), ('packets.received', 'packets_received'), ('packets.lost', 'packets_lost')]:
            self.assertEqual(points[name][0].value, UDP[field])
        for name, field in [('throughput', 'throughput_mbps'), ('transfer.duration', 'transfer_time_seconds'),
                            ('rtt', 'application_rtt_ms'), ('packet.loss', 'packet_loss_percent')]:
            self.assertEqual(points[name][0].sum, UDP[field])
        self.assertEqual(points['tests'][0].value, 1)
        for name, values in points.items():
            for point in values:
                self.assertEqual(dict(point.attributes), {'protocol': 'udp', **({'status': 'success'} if name == 'tests' else {})})
        self.assertEqual(UDP, before)
        resource = self.reader.get_metrics_data().resource_metrics[0]
        self.assertEqual(dict(resource.resource.attributes), telemetry.RESOURCE_ATTRIBUTES)
        self.assertEqual(resource.scope_metrics[0].scope.name, 'netbench.network')

    def test_failures_have_only_outcome_counts(self):
        telemetry.record_test_failure('TCP')
        telemetry.record_test_failure('udp')
        points = self.points()
        self.assertEqual(set(points), {'tests'})
        self.assertEqual(len(points['tests']), 2)
        for point in points['tests']:
            self.assertEqual(point.value, 1)
            self.assertEqual(point.attributes['status'], 'failure')

    @patch('backend.app.run_tcp_test', return_value=TCP)
    @patch('backend.app.run_udp_test', return_value=UDP)
    def test_compare_exactly_once_each(self, udp, tcp):
        response = self.client.post('/api/test/compare', json={'host': '127.0.0.1', 'size_mb': 1})
        self.assertEqual(response.status_code, 200)
        points = self.points()['tests']
        self.assertEqual({(p.attributes['protocol'], p.attributes['status']): p.value for p in points},
                         {('tcp', 'success'): 1, ('udp', 'success'): 1})
        self.assertEqual(response.json['tcp']['throughput_mbps'], TCP['throughput_mbps'])

    def test_compare_failure_semantics(self):
        for tcp_fails in (True, False):
            with self.subTest(tcp_fails=tcp_fails):
                # Separate reader/provider keeps each scenario independent.
                reader = InMemoryMetricReader()
                provider = MeterProvider(metric_readers=[reader], shutdown_on_exit=False)
                try:
                    with patch.object(telemetry, '_recorder', telemetry.NetworkMetrics(provider)), \
                         patch('backend.app.run_tcp_test', side_effect=ConnectionRefusedError() if tcp_fails else None, return_value=TCP), \
                         patch('backend.app.run_udp_test', side_effect=TimeoutError()):
                        response = self.client.post('/api/test/compare', json={'host': '127.0.0.1', 'size_mb': 1})
                    self.assertEqual(response.status_code, 503 if tcp_fails else 504)
                    metrics = {m.name: m for r in reader.get_metrics_data().resource_metrics for s in r.scope_metrics for m in s.metrics}
                    outcomes = {(p.attributes['protocol'], p.attributes['status']): p.value for p in metrics['netbench.network.tests'].data.data_points}
                    self.assertEqual(outcomes, {('tcp', 'failure'): 1} if tcp_fails else {('tcp', 'success'): 1, ('udp', 'failure'): 1})
                    for name, metric in metrics.items():
                        if name != 'netbench.network.tests':
                            self.assertTrue(all(p.attributes['protocol'] == 'tcp' for p in metric.data.data_points))
                finally:
                    provider.shutdown()

    def test_validation_is_not_a_network_attempt(self):
        self.assertEqual(self.client.post('/api/test/tcp', json={'host': '', 'size_mb': 2}).status_code, 400)
        self.assertEqual(self.points(), {})

    @patch('backend.app.run_tcp_test', return_value=TCP)
    def test_recording_exception_does_not_fail_api(self, engine):
        with patch.object(self.recorder, 'record_success', side_effect=RuntimeError('broken instrument')), self.assertLogs(telemetry._LOG, level='WARNING'):
            response = self.client.post('/api/test/tcp', json={'host': '127.0.0.1', 'size_mb': 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['bytes_transferred'], TCP['bytes_transferred'])

    @patch('backend.app.run_tcp_test', side_effect=TimeoutError('real network timeout'))
    def test_failure_recording_exception_preserves_network_error(self, engine):
        with patch.object(self.recorder, 'record_failure', side_effect=RuntimeError('broken instrument')), self.assertLogs(telemetry._LOG, level='WARNING'):
            response = self.client.post('/api/test/tcp', json={'host': '127.0.0.1', 'size_mb': 1})
        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.json['details'], 'real network timeout')

    def test_invalid_protocol_or_measurement_does_not_partially_record(self):
        with self.assertLogs(telemetry._LOG, level='WARNING'):
            telemetry.record_network_test({**TCP, 'protocol': 'COMPARE'})
            telemetry.record_network_test({**TCP, 'protocol': 'TCP', 'throughput_mbps': float('nan')})
        self.assertEqual(self.points(), {})

    @patch('backend.app.run_tcp_test', return_value=TCP)
    def test_background_exporter_failure_does_not_block_api(self, engine):
        entered, release = threading.Event(), threading.Event()
        class UnavailableExporter(MetricExporter):
            def export(self, metrics_data, timeout_millis=10000, **kwargs):
                entered.set()
                release.wait(2)
                return MetricExportResult.FAILURE
            def force_flush(self, timeout_millis=10000):
                return True
            def shutdown(self, timeout_millis=30000, **kwargs):
                pass
        reader = PeriodicExportingMetricReader(UnavailableExporter(), export_interval_millis=10)
        provider = MeterProvider(metric_readers=[reader], shutdown_on_exit=False)
        try:
            with patch.object(telemetry, '_recorder', telemetry.NetworkMetrics(provider)):
                telemetry.record_network_test({**TCP, 'protocol': 'TCP'})
                self.assertTrue(entered.wait(1))
                # Export is held by the event while the HTTP request completes.
                response = self.client.post('/api/test/tcp', json={'host': '127.0.0.1', 'size_mb': 1})
                self.assertEqual(response.status_code, 200)
                self.assertFalse(release.is_set())
        finally:
            release.set()
            provider.shutdown()

    def test_initialization_once_endpoint_and_shutdown(self):
        with patch.object(telemetry, '_initialized', False), patch.object(telemetry, '_provider', None), \
             patch.object(telemetry, '_recorder', None), patch.object(telemetry, 'OTLPMetricExporter') as exporter, \
             patch.object(telemetry, 'PeriodicExportingMetricReader'), patch.object(telemetry, 'MeterProvider') as provider, \
             patch.object(telemetry.atexit, 'register'), patch.dict('os.environ', {'OTEL_EXPORTER_OTLP_METRICS_ENDPOINT': 'http://127.0.0.1:9999/v1/metrics', 'OTEL_METRIC_EXPORT_INTERVAL': '5000'}):
            self.assertTrue(telemetry.initialize())
            self.assertTrue(telemetry.initialize())
            exporter.assert_called_once_with(endpoint='http://127.0.0.1:9999/v1/metrics', timeout=2)
            provider.assert_called_once()
            telemetry.force_flush()
            provider.return_value.force_flush.assert_called_once()
            telemetry.shutdown()
            telemetry.shutdown()
            provider.return_value.shutdown.assert_called_once()

    @patch('backend.app.run_tcp_test', return_value=TCP)
    def test_initialization_failure_leaves_api_functional(self, engine):
        with patch.object(telemetry, '_initialized', False), patch.object(telemetry, '_provider', None), \
             patch.object(telemetry, '_recorder', None), patch.object(telemetry, 'OTLPMetricExporter', side_effect=RuntimeError('bad exporter')), \
             self.assertLogs(telemetry._LOG, level='ERROR'):
            self.assertFalse(telemetry.initialize())
            response = self.client.post('/api/test/tcp', json={'host': '127.0.0.1', 'size_mb': 1})
            self.assertEqual(response.status_code, 200)
