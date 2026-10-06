"""Completed-test metrics only; network engines remain telemetry-independent."""

import atexit
import logging
import math
import os
import threading
from collections.abc import Mapping
from typing import Any

from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource

_LOG = logging.getLogger(__name__)
DEFAULT_ENDPOINT = 'http://127.0.0.1:4318/v1/metrics'
RESOURCE_ATTRIBUTES = {'service.name': 'netbench-api', 'service.version': '1.0.0'}


class NetworkMetrics:
    """Record existing measurements into an injected SDK provider, without I/O."""

    def __init__(self, provider: MeterProvider):
        meter = provider.get_meter('netbench.network')
        self.tests = meter.create_counter('netbench.network.tests', description='Number of attempted network tests.')
        self.histograms = {
            'throughput_mbps': meter.create_histogram('netbench.network.throughput', unit='Mbit/s', description='Measured network-test throughput; UDP receiver goodput.'),
            'transfer_time_seconds': meter.create_histogram('netbench.network.transfer.duration', unit='s', description='End-to-end network-test transfer duration.'),
            'application_rtt_ms': meter.create_histogram('netbench.network.rtt', unit='ms', description='Application-level request/response RTT measured by NetBench, not ICMP latency.'),
        }
        self.bytes_sent = meter.create_counter('netbench.network.bytes.sent', unit='By', description='Successfully sent test payload bytes.')
        self.bytes_received = meter.create_counter('netbench.network.bytes.received', unit='By', description='Receiver-confirmed test payload bytes.')
        self.packets = {key: meter.create_counter(f'netbench.network.packets.{suffix}', description=f'UDP DATA packets {suffix}.')
                        for key, suffix in [('packets_sent', 'sent'), ('packets_received', 'received'), ('packets_lost', 'lost')]}
        self.loss = meter.create_histogram('netbench.network.packet.loss', unit='%', description='Measured missing UDP DATA sequence percentage; not available for TCP.')

    @staticmethod
    def protocol(value: Any) -> str:
        """Constrain attributes to the two supported protocols."""
        if not isinstance(value, str) or value.lower() not in ('tcp', 'udp'):
            raise ValueError('Telemetry protocol must be TCP or UDP')
        return value.lower()

    def record_success(self, result: Mapping[str, Any]) -> None:
        """Record values unchanged; validate first to avoid partial malformed records."""
        protocol = self.protocol(result.get('protocol'))
        fields = list(self.histograms)
        fields += ['bytes_transferred'] if protocol == 'tcp' else ['bytes_sent', 'bytes_received', *self.packets, 'packet_loss_percent']
        for key in fields:
            value = result.get(key)
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError(f'Invalid telemetry measurement: {key}')
        attributes = {'protocol': protocol}
        self.tests.add(1, {**attributes, 'status': 'success'})
        for key, instrument in self.histograms.items():
            instrument.record(result[key], attributes)
        # TCP validates the final server ACK against the exact sent payload.
        # Thus bytes_transferred represents both sent and acknowledged bytes.
        self.bytes_sent.add(result['bytes_transferred'] if protocol == 'tcp' else result['bytes_sent'], attributes)
        self.bytes_received.add(result['bytes_transferred'] if protocol == 'tcp' else result['bytes_received'], attributes)
        if protocol == 'udp':
            for key, instrument in self.packets.items():
                instrument.add(result[key], attributes)
            self.loss.record(result['packet_loss_percent'], attributes)

    def record_failure(self, protocol: str) -> None:
        """Failures have an outcome counter only, never fabricated measurements."""
        self.tests.add(1, {'protocol': self.protocol(protocol), 'status': 'failure'})


_lock = threading.Lock()
_provider: MeterProvider | None = None
_recorder: NetworkMetrics | None = None
_initialized = False


def initialize() -> bool:
    """Initialize once per process at application startup, never per request.

    Uses a local SDK provider instead of overriding the global provider. This
    avoids conflicts with other instrumentation and allows isolated test readers.
    A failed setup disables recording for this process but leaves NetBench usable.
    """
    global _provider, _recorder, _initialized
    with _lock:
        if _initialized:
            return _recorder is not None
        _initialized = True
        reader = None
        try:
            interval = float(os.getenv('OTEL_METRIC_EXPORT_INTERVAL', '30000'))
            if not math.isfinite(interval) or interval <= 0:
                raise ValueError('OTEL_METRIC_EXPORT_INTERVAL must be positive milliseconds')
            exporter = OTLPMetricExporter(endpoint=os.getenv('OTEL_EXPORTER_OTLP_METRICS_ENDPOINT', DEFAULT_ENDPOINT), timeout=2)
            reader = PeriodicExportingMetricReader(exporter, export_interval_millis=interval, export_timeout_millis=2500)
            # Direct Resource avoids injecting host/process/user-specific detectors.
            _provider = MeterProvider(metric_readers=[reader], resource=Resource(RESOURCE_ATTRIBUTES), shutdown_on_exit=False)
            _recorder = NetworkMetrics(_provider)
            atexit.register(shutdown)
            return True
        except Exception:
            _LOG.exception('OpenTelemetry initialization failed; network testing remains available')
            if _provider is not None:
                try:
                    _provider.shutdown(timeout_millis=3000)
                except Exception:
                    _LOG.warning('Telemetry cleanup failed', exc_info=True)
            elif reader is not None:
                try:
                    reader.shutdown(timeout_millis=3000)
                except Exception:
                    _LOG.warning('Telemetry reader cleanup failed', exc_info=True)
            _provider = None
            _recorder = None
            return False


def record_network_test(result: Mapping[str, Any]) -> None:
    """Best-effort recording; never exports or changes a network result."""
    try:
        if _recorder is not None:
            _recorder.record_success(result)
    except Exception:
        _LOG.warning('Unable to record network-test telemetry', exc_info=True)


def record_test_failure(protocol: str) -> None:
    """Keep telemetry errors independent from the original networking exception."""
    try:
        if _recorder is not None:
            _recorder.record_failure(protocol)
    except Exception:
        _LOG.warning('Unable to record network-test failure telemetry', exc_info=True)


def force_flush(timeout_millis: float = 3000) -> bool:
    """Explicit maintenance/test hook; never called by HTTP request handlers."""
    try:
        return _provider.force_flush(timeout_millis=timeout_millis) if _provider else True
    except Exception:
        _LOG.warning('Telemetry flush failed', exc_info=True)
        return False


def shutdown() -> None:
    """Release the provider once on process exit; safe to call repeatedly."""
    global _provider, _recorder
    with _lock:
        provider, _provider = _provider, None
        _recorder = None
    if provider is not None:
        try:
            provider.shutdown(timeout_millis=3000)
        except Exception:
            _LOG.warning('Telemetry shutdown failed', exc_info=True)
