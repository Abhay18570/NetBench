# NetBench UDP terminal tests

From the project root, run the server and client in separate terminals:

```sh
.venv/bin/python -m backend.network.udp_server --host 127.0.0.1
.venv/bin/python -m backend.network.udp_client --host 127.0.0.1 --size 1
.venv/bin/python -m backend.network.udp_client --host 127.0.0.1 --size 10
```

Server defaults: `0.0.0.0:5002`. Client defaults: `127.0.0.1:5002`, 10 MB.
Both accept `--host` and `--port`; the client accepts whole-MB `--size` values
from 1 through 1024, including 1, 5, 10, 25 and 50. Here MB means 1,048,576
bytes. Payload generation uses a reusable in-memory buffer.

## Protocol

Controls are one UDP datagram containing `NBC1` followed by a JSON object with
`type` and a canonical UUID hex `id`. Controls are capped at 1,024 bytes.

1. PING/PONG measures application RTT. A fresh nonce identifies each attempt.
2. START supplies `bytes`, `packets` and `payload_size`; READY echoes the counts.
3. DATA consists of `NBD1`, a 16-byte UUID, a network-order uint32 sequence,
   and up to 1,200 payload bytes. Sequences start at zero. The final payload
   has exactly the remaining bytes. Total IPv4 packet size is at most 1,252
   bytes with ordinary headers, below a typical 1,500-byte MTU; smaller path
   MTUs can still cause fragmentation.
4. END starts a fixed 150 ms reorder window. Valid late DATA within this
   window is counted. RESULT reports unique packets and payload bytes received.

Controls get at most four attempts, each with a 750 ms response deadline.
DATA is sent once without pacing or retransmission. Duplicate START does not
reset a session; duplicate END does not extend the reorder window. Completed
RESULT is cached for retries. The server binds each UUID to its sender's IPv4
address and port. Unknown DATA and malformed datagrams are dropped.

## Metrics and limits

- Loss is `(packets_sent - unique_packets_received) / packets_sent * 100`.
  Duplicate packets do not increase either received bytes or packet counts.
- Throughput is receiver goodput: received payload bytes times eight divided
  by elapsed seconds and 1,000,000. Headers are excluded.
- Elapsed time starts before the first DATA send and ends on RESULT receipt.
  It includes sending, receiver processing, the reorder window and any END
  retries. This is not a raw link-capacity measurement.
- RTT measures successful application PING/PONG, not ICMP latency; it includes
  peer processing and scheduling. Failed attempts are excluded from RTT.
- Missing DATA can reflect network loss, local socket-buffer drops or packets
  arriving after the reorder window. This code cannot attribute the cause.
  Localhost loss can be zero or nonzero; nothing is fabricated.
- At most 16 sessions are retained. Sessions expire after 30 seconds idle or
  120 seconds total. A bitset bounds sequence tracking to roughly 112 KiB per
  maximum-size session. No payload is retained by the receiver.
- A busy server rejects new sessions; retry later after entries expire.
  Exhausted control retries fail the test rather than inventing a result.

Run compile checks and the complete suite (local socket access is required):

```sh
.venv/bin/python -m compileall -q backend/network backend/metrics backend/tests
.venv/bin/python -m unittest discover -s backend/tests -v
```
