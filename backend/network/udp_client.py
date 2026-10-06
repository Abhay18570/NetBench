"""Real UDP benchmark: retry controls, never retransmit DATA."""

import argparse
import socket
import sys
import time
import uuid
from typing import Any

from backend.metrics.calculator import UDPMetrics, calculate_udp_metrics
from .protocol import MAX_SIZE_MB, MIB, ProtocolError, valid_port, valid_size
from .udp_protocol import (
    PAYLOAD_SIZE, MAX_CONTROL_SIZE, CONTROL_ATTEMPTS, CONTROL_TIMEOUT,
    encode_control, decode_control, encode_data,
)


def exchange(sock: socket.socket, kind: str, expected: str, test_id: str,
             **fields: Any) -> tuple[dict[str, Any], float, float]:
    """Retry controls with deadlines; ignore unrelated/malformed responses.

    PING gets a fresh nonce on each retry so late PONGs cannot produce an
    artificially short RTT for a subsequent attempt.
    """
    for _ in range(CONTROL_ATTEMPTS):
        if kind == 'PING':
            fields['nonce'] = uuid.uuid4().hex
        request = encode_control(kind, test_id, **fields)
        sent = time.perf_counter()
        sock.send(request)
        deadline = sent + CONTROL_TIMEOUT
        while time.perf_counter() < deadline:
            sock.settimeout(max(0.001, deadline - time.perf_counter()))
            try:
                data = sock.recv(MAX_CONTROL_SIZE + 1)
                received = time.perf_counter()
            except socket.timeout:
                break
            try:
                reply = decode_control(data)
            except ProtocolError:
                continue
            if reply['id'] != test_id:
                continue
            if reply['type'] == 'ERROR':
                raise ProtocolError(f'Server rejected test: {reply.get("error", "unknown error")}')
            if reply['type'] == expected and (kind != 'PING' or reply.get('nonce') == fields['nonce']):
                return reply, sent, received
    raise TimeoutError(f'{kind}/{expected} timed out after {CONTROL_ATTEMPTS} attempts')


def run_test(host: str = '127.0.0.1', port: int = 5002, size_mb: int = 10) -> UDPMetrics:
    """Send exact requested payload bytes and report receiver-confirmed goodput."""
    if type(size_mb) is not int or not 1 <= size_mb <= MAX_SIZE_MB:
        raise ValueError(f'Size must be an integer between 1 and {MAX_SIZE_MB} MB')
    count = size_mb * MIB
    packets = (count + PAYLOAD_SIZE - 1) // PAYLOAD_SIZE
    test_id = uuid.uuid4().hex
    payload = b'N' * PAYLOAD_SIZE
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(CONTROL_TIMEOUT)
        # UDP connect selects a peer and filters replies; no TCP handshake occurs.
        sock.connect((host, port))
        _, ping_sent, pong_received = exchange(sock, 'PING', 'PONG', test_id)
        ready, _, _ = exchange(sock, 'START', 'READY', test_id,
                               bytes=count, packets=packets, payload_size=PAYLOAD_SIZE)
        if (type(ready.get('bytes')) is not int or type(ready.get('packets')) is not int
                or ready['bytes'] != count or ready['packets'] != packets):
            raise ProtocolError('READY metadata mismatch')
        sock.settimeout(CONTROL_TIMEOUT)
        transfer_start = time.perf_counter()
        sent_bytes = 0
        for sequence in range(packets):
            length = min(PAYLOAD_SIZE, count - sent_bytes)
            datagram = encode_data(test_id, sequence, payload[:length])
            if sock.send(datagram) != len(datagram):
                raise OSError('Incomplete UDP datagram send')
            sent_bytes += length
        result, _, transfer_end = exchange(sock, 'END', 'RESULT', test_id)

    received_bytes, received_packets = result.get('bytes_received'), result.get('packets_received')
    if (type(received_bytes) is not int or type(received_packets) is not int
            or not 0 <= received_packets <= packets or not 0 <= received_bytes <= count):
        raise ProtocolError('Invalid RESULT counts')
    # Every unique sequence has a fixed length; only the last packet is shorter.
    possible_bytes = {received_packets * PAYLOAD_SIZE}
    if received_packets:
        possible_bytes.add((received_packets - 1) * PAYLOAD_SIZE + count - (packets - 1) * PAYLOAD_SIZE)
    if received_bytes not in possible_bytes:
        raise ProtocolError('Inconsistent RESULT byte and packet counts')
    return calculate_udp_metrics(f'{host}:{port}', size_mb, sent_bytes, received_bytes,
                                 packets, received_packets, transfer_start, transfer_end,
                                 ping_sent, pong_received)


def print_results(metrics: UDPMetrics) -> None:
    """Print actual measurements with timing and loss interpretation."""
    print('\n' + '=' * 40 + '\nNetBench UDP Performance Test\n' + '=' * 40)
    for label, key in [('Server', 'server'), ('Protocol', 'protocol'), ('Test Size', 'test_size_mb'),
                       ('Bytes Sent', 'bytes_sent'), ('Bytes Received', 'bytes_received'),
                       ('Packets Sent', 'packets_sent'), ('Packets Received', 'packets_received'),
                       ('Packets Lost', 'packets_lost')]:
        print(f'{label + ":":20}{metrics[key]}' + (' MB' if key == 'test_size_mb' else ''))
    print(f'Packet Loss:        {metrics["packet_loss_percent"]:.2f}%')
    print(f'Transfer Time:      {metrics["transfer_time_seconds"]:.6f} s')
    print(f'Throughput:         {metrics["throughput_mbps"]:.2f} Mbps')
    print(f'Application RTT:    {metrics["application_rtt_ms"]:.3f} ms')
    print('=' * 40)
    print('Receiver goodput; payload bytes only. 1 MB = 1,048,576 bytes.')
    print('Elapsed time includes END/RESULT, control retries and a 150 ms reorder window.')
    print('Application RTT is not ICMP latency. Loss is missing DATA sequences, not measured IP loss.')


def main() -> int:
    """Run a UDP test from the terminal."""
    parser = argparse.ArgumentParser(description='NetBench real UDP performance test')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=valid_port, default=5002)
    parser.add_argument('--size', type=valid_size, default=10, help='Whole MB, 1–1024 (default: 10)')
    args = parser.parse_args()
    try:
        print_results(run_test(args.host, args.port, args.size))
    except (OSError, ValueError) as exc:
        print(f'UDP test failed: {exc}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('\nUDP test cancelled.', file=sys.stderr)
        return 130
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
