"""Public, failure-isolated OpenTelemetry metrics API for Flask orchestration."""

from .metrics import initialize, record_network_test, record_test_failure, force_flush, shutdown

__all__ = ['initialize', 'record_network_test', 'record_test_failure', 'force_flush', 'shutdown']
