"""Real TCP performance client; no Flask or frontend integration."""

import argparse
import socket
import sys
import time

from backend.metrics.calculator import TCPMetrics, calculate_metrics
from .protocol import (
    CHUNK_SIZE, MAX_SIZE_MB, MIB, SOCKET_TIMEOUT, ProtocolError,
    expect_message, send_message, valid_port, valid_size,
)


def run_test(host: str = '127.0.0.1', port: int = 5001, size_mb: int = 10) -> TCPMetrics:
    """Measure bulk transfer through final ACK and a separate application RTT."""
    if type(size_mb) is not int or not 1 <= size_mb <= MAX_SIZE_MB:
        raise ValueError(f'Size must be an integer between 1 and {MAX_SIZE_MB} MB')
    expected = size_mb * MIB
    # Reuse an in-memory chunk, keeping memory bounded even for larger tests.
    payload = b'N' * CHUNK_SIZE
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.settimeout(SOCKET_TIMEOUT)
        connection.connect((host, port))
        send_message(connection, {'type': 'METADATA', 'bytes': expected})
        ready = expect_message(connection, 'READY')
        if type(ready.get('bytes')) is not int or ready['bytes'] != expected:
            raise ProtocolError('Server acknowledged a different metadata byte count')

        ping_sent = time.perf_counter()
        send_message(connection, {'type': 'PING'})
        expect_message(connection, 'PONG')
        pong_received = time.perf_counter()

        transfer_start = time.perf_counter()
        remaining = expected
        while remaining:
            count = min(remaining, CHUNK_SIZE)
            connection.sendall(payload[:count])
            remaining -= count
        complete = expect_message(connection, 'COMPLETE')
        transfer_end = time.perf_counter()
        if type(complete.get('bytes')) is not int or complete['bytes'] != expected:
            raise ProtocolError('Final acknowledgement byte count does not match payload')

    return calculate_metrics(expected, transfer_start, transfer_end, ping_sent, pong_received)


def print_results(host: str, port: int, size: int, metrics: TCPMetrics) -> None:
    """Print measured values and their application-level interpretation."""
    print('\n' + '=' * 40)
    print('NetBench TCP Performance Test')
    print('=' * 40)
    print(f'\nServer:            {host}:{port}')
    print('Protocol:          TCP')
    print(f'Test Size:         {size} MB')
    print(f'Bytes Transferred: {metrics["bytes_transferred"]}')
    print(f'Transfer Time:     {metrics["transfer_time_seconds"]:.6f} s')
    print(f'Throughput:        {metrics["throughput_mbps"]:.2f} Mbps')
    print(f'Application RTT:   {metrics["application_rtt_ms"]:.3f} ms')
    print('Packet Loss:       N/A')
    print('\n' + '=' * 40)
    print('1 MB = 1,048,576 bytes. Transfer time includes the final server ACK.')
    print('Application-level RTT includes server processing; IP packet loss is not measured.')


def main() -> int:
    """Run a terminal benchmark using command-line settings."""
    parser = argparse.ArgumentParser(description='NetBench real TCP performance test')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=valid_port, default=5001)
    parser.add_argument('--size', type=valid_size, default=10, help='Whole MB, 1–1024 (default: 10)')
    args = parser.parse_args()
    try:
        metrics = run_test(args.host, args.port, args.size)
    except (OSError, ConnectionError, ValueError) as exc:
        print(f'TCP test failed: {exc}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('\nTCP test cancelled.', file=sys.stderr)
        return 130
    print_results(args.host, args.port, args.size, metrics)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
