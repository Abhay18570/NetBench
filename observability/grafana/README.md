# NetBench dashboard panel reference

Source of truth: `dashboards/netbench-overview.json`. Every data panel uses the
provisioned `prometheus` UID. Both protocols remain visible; UDP reliability
panels deliberately have no TCP query. The reading-notes text panel explains
measurement limits. Five rows separate overview, throughput/RTT, transfer,
UDP reliability, and activity.

Stat panels use current cumulative counters/means since SDK startup. Charts
use rolling histogram increases with a minimum two-minute rate window,
chosen to cover multiple 30-second SDK exports. Gaps with no new observations
are preserved rather than filled with fabricated zeros. These are not latest-test
gauges. All expressions are directly validated with `$__rate_interval=2m`.

## Total Successful Tests

Cumulative observations since the current Flask SDK process started, not the latest test and not a total limited to the selected dashboard time range. Compare contributes one TCP and one UDP test.

Successful tests:

```promql
sum(netbench_network_tests_total{job="netbench",status="success"})
```

## Successful Tests by Protocol

Cumulative observations since the current Flask SDK process started, not the latest test and not a total limited to the selected dashboard time range.

TCP:

```promql
sum(netbench_network_tests_total{job="netbench",status="success",protocol="tcp"})
```

UDP:

```promql
sum(netbench_network_tests_total{job="netbench",status="success",protocol="udp"})
```

## Average Throughput

Cumulative observations since the current Flask SDK process started, not the latest test and not a total limited to the selected dashboard time range. Mean Mbps; UDP is receiver goodput.

TCP:

```promql
sum(netbench_network_throughput_Mbit_per_second_sum{job="netbench",protocol="tcp"}) / (sum(netbench_network_throughput_Mbit_per_second_count{job="netbench",protocol="tcp"}) > 0)
```

UDP:

```promql
sum(netbench_network_throughput_Mbit_per_second_sum{job="netbench",protocol="udp"}) / (sum(netbench_network_throughput_Mbit_per_second_count{job="netbench",protocol="udp"}) > 0)
```

## Average Application RTT

Cumulative observations since the current Flask SDK process started, not the latest test and not a total limited to the selected dashboard time range. Application request/response including peer processing; not ICMP ping.

TCP:

```promql
sum(netbench_network_rtt_milliseconds_sum{job="netbench",protocol="tcp"}) / (sum(netbench_network_rtt_milliseconds_count{job="netbench",protocol="tcp"}) > 0)
```

UDP:

```promql
sum(netbench_network_rtt_milliseconds_sum{job="netbench",protocol="udp"}) / (sum(netbench_network_rtt_milliseconds_count{job="netbench",protocol="udp"}) > 0)
```

## Throughput over Time

Rolling per-test mean from histogram increases over $__rate_interval (at least 2 minutes). Gaps mean no new observations in the window, not zero performance. SDK exports every 30 seconds; values are not instantaneous link speed.

TCP:

```promql
sum(increase(netbench_network_throughput_Mbit_per_second_sum{job="netbench",protocol="tcp"}[$__rate_interval])) / (sum(increase(netbench_network_throughput_Mbit_per_second_count{job="netbench",protocol="tcp"}[$__rate_interval])) > 0)
```

UDP:

```promql
sum(increase(netbench_network_throughput_Mbit_per_second_sum{job="netbench",protocol="udp"}[$__rate_interval])) / (sum(increase(netbench_network_throughput_Mbit_per_second_count{job="netbench",protocol="udp"}[$__rate_interval])) > 0)
```

## Application RTT over Time

Rolling per-test mean from histogram increases over $__rate_interval (at least 2 minutes). Gaps mean no new observations in the window, not zero performance. SDK exports every 30 seconds; values are not instantaneous link speed. Application RTT, not ICMP.

TCP:

```promql
sum(increase(netbench_network_rtt_milliseconds_sum{job="netbench",protocol="tcp"}[$__rate_interval])) / (sum(increase(netbench_network_rtt_milliseconds_count{job="netbench",protocol="tcp"}[$__rate_interval])) > 0)
```

UDP:

```promql
sum(increase(netbench_network_rtt_milliseconds_sum{job="netbench",protocol="udp"}[$__rate_interval])) / (sum(increase(netbench_network_rtt_milliseconds_count{job="netbench",protocol="udp"}[$__rate_interval])) > 0)
```

## Average Transfer Duration

Cumulative observations since the current Flask SDK process started, not the latest test and not a total limited to the selected dashboard time range. TCP includes final ACK; UDP includes 150 ms reorder window and control exchange/retries. Durations have different semantics.

TCP:

```promql
sum(netbench_network_transfer_duration_seconds_sum{job="netbench",protocol="tcp"}) / (sum(netbench_network_transfer_duration_seconds_count{job="netbench",protocol="tcp"}) > 0)
```

UDP:

```promql
sum(netbench_network_transfer_duration_seconds_sum{job="netbench",protocol="udp"}) / (sum(netbench_network_transfer_duration_seconds_count{job="netbench",protocol="udp"}) > 0)
```

## Payload Bytes Sent & Received

Cumulative observations since the current Flask SDK process started, not the latest test and not a total limited to the selected dashboard time range. Payload bytes only. TCP received count is validated by final ACK; UDP received bytes are unique DATA payloads.

TCP · Sent:

```promql
sum(netbench_network_bytes_sent_total{job="netbench",protocol="tcp"})
```

TCP · Received:

```promql
sum(netbench_network_bytes_received_total{job="netbench",protocol="tcp"})
```

UDP · Sent:

```promql
sum(netbench_network_bytes_sent_total{job="netbench",protocol="udp"})
```

UDP · Received:

```promql
sum(netbench_network_bytes_received_total{job="netbench",protocol="udp"})
```

## Average UDP Packet Loss

Cumulative observations since the current Flask SDK process started, not the latest test and not a total limited to the selected dashboard time range. Arithmetic mean of per-test loss percentages, not packet-weighted loss. TCP unavailable.

UDP:

```promql
sum(netbench_network_packet_loss_percent_sum{job="netbench",protocol="udp"}) / (sum(netbench_network_packet_loss_percent_count{job="netbench",protocol="udp"}) > 0)
```

## UDP DATA Packets

Cumulative observations since the current Flask SDK process started, not the latest test and not a total limited to the selected dashboard time range. Received counts unique sequence numbers. No TCP packet statistics.

Sent:

```promql
sum(netbench_network_packets_sent_total{job="netbench",protocol="udp"})
```

Received:

```promql
sum(netbench_network_packets_received_total{job="netbench",protocol="udp"})
```

Lost:

```promql
sum(netbench_network_packets_lost_total{job="netbench",protocol="udp"})
```

## UDP Packet Loss over Time

Rolling per-test mean from histogram increases over $__rate_interval (at least 2 minutes). Gaps mean no new observations in the window, not zero performance. SDK exports every 30 seconds; values are not instantaneous link speed. UDP-only mean per-test percentage, not a TCP loss estimate.

UDP:

```promql
sum(increase(netbench_network_packet_loss_percent_sum{job="netbench",protocol="udp"}[$__rate_interval])) / (sum(increase(netbench_network_packet_loss_percent_count{job="netbench",protocol="udp"}[$__rate_interval])) > 0)
```

## Successful Test Activity over Time

Estimated successful test increases per rolling $__rate_interval window. Prometheus extrapolation can produce fractional counts. Resets are handled by increase; the first sample alone cannot establish an increase.

TCP:

```promql
sum(increase(netbench_network_tests_total{job="netbench",status="success",protocol="tcp"}[$__rate_interval]))
```

UDP:

```promql
sum(increase(netbench_network_tests_total{job="netbench",status="success",protocol="udp"}[$__rate_interval]))
```

