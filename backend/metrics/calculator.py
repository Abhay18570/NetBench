"""Reusable calculations for real TCP application-level measurements."""

import math
from typing import TypedDict


class TCPMetrics(TypedDict):
    bytes_transferred: int
    transfer_time_seconds: float
    throughput_mbps: float
    application_rtt_ms: float
    packet_loss_percent: None


def transfer_time_seconds(start: float, end: float) -> float:
    """Return elapsed seconds from two monotonic perf_counter timestamps."""
    if not math.isfinite(start) or not math.isfinite(end) or end <= start:
        raise ValueError('Timestamps must be finite and end must be after start')
    return end - start


def throughput_mbps(bytes_transferred: int, duration: float) -> float:
    """Convert acknowledged application bytes per second to decimal Mbps."""
    if type(bytes_transferred) is not int or bytes_transferred < 0:
        raise ValueError('Byte count must be a nonnegative integer')
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('Transfer duration must be finite and positive')
    return bytes_transferred * 8 / (duration * 1_000_000)


def application_rtt_ms(ping_sent: float, pong_received: float) -> float:
    """Return application-level ping/pong RTT, including peer processing."""
    return transfer_time_seconds(ping_sent, pong_received) * 1000


def calculate_metrics(
    bytes_transferred: int,
    transfer_start: float,
    transfer_end: float,
    ping_sent: float,
    pong_received: float,
) -> TCPMetrics:
    """Calculate metrics without implying measurement of TCP/IP packet loss."""
    duration = transfer_time_seconds(transfer_start, transfer_end)
    return {
        'bytes_transferred': bytes_transferred,
        'transfer_time_seconds': duration,
        'throughput_mbps': throughput_mbps(bytes_transferred, duration),
        'application_rtt_ms': application_rtt_ms(ping_sent, pong_received),
        # TCP socket byte delivery cannot directly reveal underlying IP packet
        # loss or retransmissions. Successful delivery does not imply 0% loss.
        'packet_loss_percent': None,
    }


class UDPMetrics(TypedDict):
    protocol: str
    server: str
    test_size_mb: int
    bytes_sent: int
    bytes_received: int
    packets_sent: int
    packets_received: int
    packets_lost: int
    packet_loss_percent: float
    transfer_time_seconds: float
    throughput_mbps: float
    application_rtt_ms: float


def udp_packet_loss(packets_sent: int, unique_packets_received: int) -> tuple[int, float]:
    """Calculate loss from unique, validated DATA sequence numbers only."""
    if (type(packets_sent) is not int or type(unique_packets_received) is not int
            or packets_sent <= 0 or not 0 <= unique_packets_received <= packets_sent):
        raise ValueError('Invalid UDP packet counts')
    lost = packets_sent - unique_packets_received
    return lost, lost / packets_sent * 100


def calculate_udp_metrics(
    server: str, test_size_mb: int, bytes_sent: int, bytes_received: int,
    packets_sent: int, packets_received: int, transfer_start: float,
    transfer_end: float, ping_sent: float, pong_received: float,
) -> UDPMetrics:
    """Receiver goodput over client elapsed time, including END/RESULT and grace.

    RTT is an application exchange, not ICMP latency. DATA headers are excluded
    from byte counts. Control retries, if needed, are included in elapsed time.
    """
    if (type(bytes_sent) is not int or type(bytes_received) is not int
            or bytes_sent <= 0 or not 0 <= bytes_received <= bytes_sent):
        raise ValueError('Invalid UDP byte counts')
    lost, loss = udp_packet_loss(packets_sent, packets_received)
    duration = transfer_time_seconds(transfer_start, transfer_end)
    return {
        'protocol': 'UDP', 'server': server, 'test_size_mb': test_size_mb,
        'bytes_sent': bytes_sent, 'bytes_received': bytes_received,
        'packets_sent': packets_sent, 'packets_received': packets_received,
        'packets_lost': lost, 'packet_loss_percent': loss,
        'transfer_time_seconds': duration,
        'throughput_mbps': throughput_mbps(bytes_received, duration),
        'application_rtt_ms': application_rtt_ms(ping_sent, pong_received),
    }
