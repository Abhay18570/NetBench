"""Sequential TCP benchmark server. Run from the project root with -m."""

import argparse
import socket
import sys

from .protocol import (
    CHUNK_SIZE, MAX_SIZE_MB, MIB, SOCKET_TIMEOUT, ProtocolError,
    expect_message, send_message, valid_port,
)


def handle_client(connection: socket.socket) -> None:
    """Acknowledge metadata, answer ping, receive payload and confirm bytes."""
    connection.settimeout(SOCKET_TIMEOUT)
    metadata = expect_message(connection, 'METADATA')
    expected = metadata.get('bytes')
    if type(expected) is not int or not 1 <= expected <= MAX_SIZE_MB * MIB:
        raise ProtocolError(f'Expected byte count must be between 1 and {MAX_SIZE_MB * MIB}')
    print(f'Expected data: {expected / MIB:g} MB ({expected} bytes)', flush=True)
    send_message(connection, {'type': 'READY', 'bytes': expected})
    expect_message(connection, 'PING')
    send_message(connection, {'type': 'PONG'})

    received = 0
    while received < expected:
        chunk = connection.recv(min(CHUNK_SIZE, expected - received))
        if not chunk:
            raise ConnectionError(f'Client disconnected: received {received} of {expected} bytes')
        received += len(chunk)
    print(f'Received: {received} bytes\nTransfer completed', flush=True)
    send_message(connection, {'type': 'COMPLETE', 'bytes': received})
    print('Acknowledgement sent', flush=True)


def serve(host: str = '0.0.0.0', port: int = 5001) -> None:
    """Serve sequential tests until interrupted; isolate individual peer failures."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((host, port))
        listener.listen(5)
        listener.settimeout(1.0)
        print(f'NetBench TCP Server\nListening on {host}:{port}', flush=True)
        while True:
            try:
                connection, address = listener.accept()
            except socket.timeout:
                continue
            with connection:
                print(f'\nClient connected: {address[0]}:{address[1]}', flush=True)
                try:
                    handle_client(connection)
                except (OSError, ConnectionError, ProtocolError) as exc:
                    print(f'Test failed: {exc}. Connection closed; ready for next test.', flush=True)


def main() -> int:
    """Parse arguments and launch the TCP listener."""
    parser = argparse.ArgumentParser(description='NetBench TCP benchmark server')
    parser.add_argument('--host', default='0.0.0.0', help='IPv4 bind address (default: 0.0.0.0)')
    parser.add_argument('--port', type=valid_port, default=5001)
    args = parser.parse_args()
    try:
        serve(args.host, args.port)
    except KeyboardInterrupt:
        print('\nTCP server stopped.', flush=True)
    except OSError as exc:
        print(f'TCP server error: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
