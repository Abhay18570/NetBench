"""Local HTTP API invoking independent, already-running TCP/UDP services."""

import socket
import threading

from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.exceptions import BadRequest, UnsupportedMediaType, RequestEntityTooLarge

from backend.network.tcp_client import run_test as run_tcp_test
from backend.network.udp_client import run_test as run_udp_test
from backend.network.protocol import ProtocolError
from backend import telemetry

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 4096
CORS(app, resources={r'/api/*': {'origins': [
    'http://localhost:5173', 'http://127.0.0.1:5173',
]}})
# Avoid overlapping benchmark requests in this local single-process service.
_test_lock = threading.Lock()
ALLOWED_SIZES = {1, 5, 10, 25, 50}


@app.get('/api/health')
def health() -> dict[str, str]:
    """Report Flask availability only, not benchmark server availability."""
    return {'status': 'ok', 'service': 'NetBench API'}


def parse_config() -> tuple[str, int]:
    """Validate JSON without accepting bools/floats as integer test sizes."""
    data = request.get_json()
    if not isinstance(data, dict):
        raise ValueError('Request body must be a JSON object')
    host, size = data.get('host'), data.get('size_mb')
    if (not isinstance(host, str) or not host.strip() or len(host) > 253
            or any(char.isspace() or ord(char) < 32 for char in host.strip())
            or any(char in host for char in '/:\\')):
        raise ValueError('host must be a non-empty IPv4 address or hostname without a URL or port')
    if type(size) is not int or size not in ALLOWED_SIZES:
        raise ValueError('size_mb must be one of: 1, 5, 10, 25, 50')
    return host.strip(), size


def run_protocol(protocol: str, host: str, size: int) -> dict:
    """Map existing engine output to the public response without rounding."""
    port = 5001 if protocol == 'TCP' else 5002
    engine = run_tcp_test if protocol == 'TCP' else run_udp_test
    try:
        metrics = engine(host=host, port=port, size_mb=size)
    except Exception:
        telemetry.record_test_failure(protocol)
        raise
    result = {**metrics, 'protocol': protocol, 'host': host, 'port': port, 'test_size_mb': size}
    telemetry.record_network_test(result)
    return result


def test_response(protocols: tuple[str, ...]):
    """Execute requested engines sequentially and surface failures as JSON."""
    try:
        host, size = parse_config()
    except (BadRequest, UnsupportedMediaType, ValueError) as exc:
        return jsonify(error='Invalid test request', details=str(exc)), 400
    if not _test_lock.acquire(blocking=False):
        return jsonify(error='A network test is already running', details='Wait for it to finish before retrying.'), 409
    results = {}
    current = protocols[0]
    try:
        for current in protocols:
            results[current.lower()] = run_protocol(current, host, size)
        return jsonify(results if len(protocols) > 1 else results[current.lower()])
    except socket.gaierror as exc:
        status, message = 400, f'Invalid or unresolvable host: {host}'
        details = str(exc)
    except TimeoutError as exc:
        status, message, details = 504, f'{current} test timed out', str(exc)
    except ConnectionRefusedError as exc:
        status, message, details = 503, f'{current} test server is unavailable', str(exc)
    except (OSError, ProtocolError, ValueError) as exc:
        status, message, details = 502, f'{current} network test failed', str(exc)
    except Exception:
        app.logger.exception('Unexpected benchmark failure')
        status, message, details = 500, f'{current} network test failed', 'Unexpected server error; check the Flask logs.'
    finally:
        _test_lock.release()
    # Never return a successful comparison with partial or fabricated metrics.
    return jsonify(error=message, details=details, failed_protocol=current,
                   completed_protocols=[name.upper() for name in results]), status


@app.post('/api/test/tcp')
def tcp_test():
    """Run the TCP client against port 5001."""
    return test_response(('TCP',))


@app.post('/api/test/udp')
def udp_test():
    """Run the UDP client against port 5002."""
    return test_response(('UDP',))


@app.post('/api/test/compare')
def compare_test():
    """Run TCP then UDP against the same host and test size."""
    return test_response(('TCP', 'UDP'))


@app.errorhandler(RequestEntityTooLarge)
def oversized_request(_error):
    """Keep oversized-body failures in the API JSON error format."""
    return jsonify(error='Request body too large', details='Limit: 4096 bytes.'), 413


if __name__ == '__main__':
    telemetry.initialize()
    try:
        app.run(host='127.0.0.1', port=5000, use_reloader=False)
    finally:
        telemetry.shutdown()
