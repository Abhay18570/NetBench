# Phase 10 — Final integration and demo readiness

## 1. Overall status: PASS

Validated on **7 October 2026**, on one Mac using **127.0.0.1 only**. The full
matrix ran at **04:15:40–04:15:43 UTC (09:45:40–09:45:43 IST)**. All 15 actual
browser operations returned HTTP 200, producing 20 real protocol results.
Outage, recovery, persistence, regression, and README-only fresh-start checks passed.
Services were left running for the demo; the actual Vite URL is **http://localhost:5173**.

Evidence: [unrounded responses and validation data](phase10-results.json).
This is a recorded validation run, not a promise of identical future throughput.

## 2–4. Files and application changes

Created:

- `docs/phase10-loopback-results.md` — this report.
- `docs/phase10-results.json` — raw measurements and validation evidence.

Modified: `README.md` only. **No application code changed in Phase 10.** No
reproducible application defect was found. Networking, metric formulas, UI,
telemetry, dependencies, image pins, and Vite `/api` proxy remain unchanged.
Temporary browser tooling and verification scripts were kept outside the repo;
project dependencies were not upgraded or added.

## 5. Environment

| Component | Observed version |
|---|---|
| macOS / architecture | 26.5 (25F71) / arm64 |
| Python (root `.venv`) | 3.14.7 |
| Node | 26.8.1 |
| npm | 11.19.0 |
| Docker | 29.7.2, build a7dcaa6 |
| Docker Compose | v5.4.0 |
| Collector | otel/opentelemetry-collector-contrib:0.161.0 |
| Prometheus | prom/prometheus:v3.15.0 |
| Grafana | grafana/grafana:13.2.3 |
| OTel SDK / HTTP exporter | 1.45.0 |
| Flask | 3.1.3 |
| Vite | 8.3.3 |
| Automated browser | Chromium 153.0.8010.12, Playwright revision 1243 |

Existing image IDs: Collector `fd328de25524`, Prometheus `efd719c99d83`, Grafana
`b28bae15e219`, all linux/arm64. No image versions changed.

## 6–10. Configuration, services, and health

| Check | Result |
|---|---|
| `docker compose config --quiet` | PASS, exit 0 |
| `netbench-otel-collector` | Running, restart count 0 |
| `netbench-prometheus` | Running, restart count 0 |
| `netbench-grafana` | Running, restart count 0 |
| Direct `http://127.0.0.1:5000/api/health` | HTTP 200 |
| Proxy `http://localhost:5173/api/health` | HTTP 200 |
| Browser health indicator | API Online from real `/api/health` |
| Native TCP / UDP | Listening on 127.0.0.1:5001 / :5002 |

Both health responses were `{"service":"NetBench API","status":"ok"}`.
All recorded browser API requests used its own Vite origin and `/api` path.
Ports were inspected before startup: no NetBench processes were running; macOS
ControlCenter occupied wildcard port 5000 and was left alone. Docker Desktop
and the existing containers were started without replacing configuration.

## 11. Complete standalone TCP results — PASS

1 MB = 1,048,576 bytes. Table numbers are rounded only for readability; JSON
preserves the actual API numbers. TCP acknowledged bytes map to both sent and
received payload bytes. TCP packet columns are unavailable, not zero.

| Size MB | Protocol | Bytes sent | Bytes received | Packets sent | Packets received | Packets lost | Duration s | Throughput Mbps | App RTT ms | Loss % |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | TCP | 1048576 | 1048576 | N/A | N/A | N/A | 0.000354666 | 23652.134687 | 0.100166 | N/A |
| 5 | TCP | 5242880 | 5242880 | N/A | N/A | N/A | 0.001082916 | 38731.572902 | 0.106208 | N/A |
| 10 | TCP | 10485760 | 10485760 | N/A | N/A | N/A | 0.001975458 | 42464.117182 | 0.079417 | N/A |
| 25 | TCP | 26214400 | 26214400 | N/A | N/A | N/A | 0.005127416 | 40900.757809 | 0.092167 | N/A |
| 50 | TCP | 52428800 | 52428800 | N/A | N/A | N/A | 0.011268084 | 37222.867703 | 0.072583 | N/A |

## 12. Complete standalone UDP results — PASS

| Size MB | Protocol | Bytes sent | Bytes received | Packets sent | Packets received | Packets lost | Duration s | Throughput Mbps | App RTT ms | Loss % |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | UDP | 1048576 | 1048576 | 874 | 874 | 0 | 0.173021125 | 48.483143 | 0.516625 | 0.000000 |
| 5 | UDP | 5242880 | 5242880 | 4370 | 4370 | 0 | 0.187711625 | 223.444020 | 0.134291 | 0.000000 |
| 10 | UDP | 10485760 | 9574960 | 8739 | 7980 | 759 | 0.203566583 | 376.288087 | 0.142208 | 8.685204 |
| 25 | UDP | 26214400 | 24506800 | 21846 | 20423 | 1423 | 0.239953500 | 817.051637 | 0.102125 | 6.513778 |
| 50 | UDP | 52428800 | 48821600 | 43691 | 40685 | 3006 | 0.300207708 | 1301.008567 | 0.132375 | 6.880135 |

## 13–14. Complete Compare results and consolidated measurement table — PASS

Every Compare displayed one TCP column and one UDP column. All nine displayed
table metrics were checked against their corresponding raw protocol response,
including formatting, bytes, packets, and TCP N/A values. Single-protocol tests
were similarly checked. Each Compare recorded one success per protocol.

| Size MB | Protocol | Bytes sent | Bytes received | Packets sent | Packets received | Packets lost | Duration s | Throughput Mbps | App RTT ms | Loss % |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | TCP | 1048576 | 1048576 | N/A | N/A | N/A | 0.000403958 | 20766.040034 | 0.142000 | N/A |
| 1 | UDP | 1048576 | 1048576 | 874 | 874 | 0 | 0.172880083 | 48.522698 | 0.219750 | 0.000000 |
| 5 | TCP | 5242880 | 5242880 | N/A | N/A | N/A | 0.000992542 | 42258.201668 | 0.092750 | N/A |
| 5 | UDP | 5242880 | 5242880 | 4370 | 4370 | 0 | 0.188182333 | 222.885110 | 0.199375 | 0.000000 |
| 10 | TCP | 10485760 | 10485760 | N/A | N/A | N/A | 0.002442958 | 34337.913301 | 0.120916 | N/A |
| 10 | UDP | 10485760 | 9501760 | 8739 | 7919 | 820 | 0.201804000 | 376.672811 | 0.227375 | 9.383225 |
| 25 | TCP | 26214400 | 26214400 | N/A | N/A | N/A | 0.005347667 | 39216.204001 | 0.105458 | N/A |
| 25 | UDP | 26214400 | 24815200 | 21846 | 20680 | 1166 | 0.239504583 | 828.884347 | 0.189125 | 5.337362 |
| 50 | TCP | 52428800 | 52428800 | N/A | N/A | N/A | 0.009581042 | 43777.117353 | 0.104417 | N/A |
| 50 | UDP | 52428800 | 48609200 | 43691 | 40508 | 3183 | 0.296821042 | 1310.128141 | 0.103541 | 7.285253 |

## 15–17. Loss, scaling, and measurement semantics — PASS

UDP loss was 0% at 1 and 5 MB. Standalone 10/25/50 MB runs lost
759/1423/3006 DATA packets; Compare runs lost 820/1166/3183 respectively.
The largest observed loss was **9.383225%** (Compare 10 MB).
**No artificial loss, delay, packet-drop simulation, or behavior adjustment was introduced.**

All requested TCP byte counts matched exactly. All durations were positive;
throughput/goodput and RTT were nonnegative. UDP received bytes and packet counts
never exceeded sent counts; lost packets equaled sent minus received; percentages
matched those counts and stayed within 0–100%. No impossible values were found.
Throughput was not required to increase monotonically.

TCP loss remained `null` in the API and **N/A** in the UI; no TCP UDP-packet
fields were returned. Prometheus query
`{__name__=~"netbench_network_packet.*",protocol="tcp",job="netbench"}` returned
no series. NetBench does not measure kernel retransmissions or IP packet-loss
events through application TCP sockets. TCP reliability does not imply that
underlying packet loss was measured as zero.

UDP goodput uses received payload bytes. Its duration includes the **150 ms
reorder/collection window**, control exchanges, and any control retries. TCP
bulk-transfer duration includes the final acknowledgement. Application RTT is
not ICMP ping. These semantics were preserved.

## 18–20. SDK, Collector, and Prometheus — PASS

The SDK exported real completed tests using the unchanged background OTLP/HTTP
pipeline. Collector detailed debug logs contained meter `netbench.network`, the
NetBench resource, both protocols, and the actual instruments. The Prometheus
Collector target was UP. The ten expected instrument families were queryable:

- `netbench_network_tests_total`
- `netbench_network_throughput_Mbit_per_second` (`_bucket`, `_sum`, `_count`)
- `netbench_network_transfer_duration_seconds` (`_bucket`, `_sum`, `_count`)
- `netbench_network_rtt_milliseconds` (`_bucket`, `_sum`, `_count`)
- `netbench_network_bytes_sent_total`
- `netbench_network_bytes_received_total`
- `netbench_network_packets_sent_total`
- `netbench_network_packets_received_total`
- `netbench_network_packets_lost_total`
- `netbench_network_packet_loss_percent` (`_bucket`, `_sum`, `_count`)

Before the matrix, the newly started SDK had no current series. After export and
scrape, successful counters were **TCP 10 / UDP 10**. Histogram observation counts
were 10 per protocol and UDP loss count 10. The 15 UI operations therefore
produced exactly the expected 20 protocol observations, with no double counting.
Exported byte and UDP packet totals matched the raw matrix exactly:

| Protocol | Bytes sent | Bytes received | Packets sent | Packets received | Packets lost |
|---|---|---|---|---|---|
| TCP | 190840832 | 190840832 | N/A | N/A | N/A |
| UDP | 190840832 | 178412432 | 159040 | 148683 | 10357 |

Subsequent outage/recovery tests are separate from this matrix baseline. Flask
restarts reset SDK counters; previously exported label combinations can remain
visible briefly. Historical data and fresh current counts are distinguished.

## 21. Grafana — PASS

Data source UID `prometheus` returned status `OK`. Dashboard UID
`netbench-overview` remained provisioned, with its correct title and measurement
notes. All 24 query targets returned without errors, and all 12 data panels
contained numeric data. A browser opened and scrolled through every panel:

1. Total Successful Tests — PASS
2. Successful Tests by Protocol — PASS
3. Average Throughput — PASS
4. Average Application RTT — PASS
5. Throughput over Time — PASS
6. Application RTT over Time — PASS
7. Average Transfer Duration — PASS
8. Payload Bytes Sent & Received — PASS
9. Average UDP Packet Loss — PASS
10. UDP DATA Packets — PASS
11. UDP Packet Loss over Time — PASS
12. Successful Test Activity over Time — PASS

The initial matrix completed within one SDK export interval. Rolling increase
panels initially had no increase to calculate; later real Compare tests and
exports supplied the additional observations. Numeric chart data was then
verified without filling gaps or changing queries. Grafana shows aggregate/history
views; React shows individual test results. React's observability status cards
remain placeholders, not probes of the working observability pipeline.

## 22–27. Controlled outages — PASS

Services were stopped one at a time and restored afterward. Each failure check
asserted an error alert, no result context, placeholder table cells instead of
fake measurements, a usable Start button, and no JavaScript runtime exception.

| Stopped component | Actual test / response | Observed behavior and recovery |
|---|---|---|
| Flask | Compare 1 MB, HTTP 403 | API Offline; useful Flask/proxy error, no result. macOS AirPlay answered the vacant wildcard port. The same open page returned to API Online through normal polling after Flask restarted. |
| TCP server | TCP 1 MB, HTTP 503 | `TCP test server is unavailable`, connection refused, empty completed protocols; restored TCP. |
| UDP server | UDP 1 MB, HTTP 503 | `UDP test server is unavailable`, connection refused, empty completed protocols; restored UDP. |
| Collector | Compare 1 MB, HTTP 200 | Both actual transfers succeeded. Background exporter logged connection refused / export timeout; tests remained functional. Restored Collector; later debug metrics confirmed delivery resumed. |
| Prometheus | Compare 1 MB, HTTP 200 | Both transfers succeeded; Collector detailed debug exports continued. Grafana data-source health reported ERROR querying Prometheus. Restored Prometheus; target UP and Grafana health OK. |
| Grafana | Compare 1 MB, HTTP 200 | Both transfers succeeded with Collector/Prometheus running. Restarted Grafana; provisioned dashboard returned. |

Compare's existing TCP-first, stop-on-failure behavior was preserved and remains
covered by regression tests; no partial comparison is labeled successful.

## 28–29. Persistence and provisioning — PASS

A nonempty `netbench_network_tests_total{job="netbench"}[1m]` historical range
was captured at a fixed pre-restart timestamp. Re-querying that **same timestamp**
after Prometheus stop/start, explicit restart, and the full fresh start returned
exactly the saved series and samples. Both copies and the query timestamp are
in the JSON evidence. This verifies old data, not merely newly scraped samples.

Grafana restarted successfully, retained the provisioned dashboard, reported a
healthy Prometheus data source, and queried the preserved historical data.
All three container restart counts were zero; no restart loop was observed.
No named volume was removed and `docker compose down -v` was never run.

## 30–34. Regression and browser checks — PASS

| Check | Result |
|---|---|
| `.venv/bin/python -m unittest discover -s backend/tests -v` | **38 tests, 0 failures**, OK |
| `.venv/bin/python -m compileall -q backend` | PASS |
| `npm run build` | PASS |
| `npm run lint` | PASS |
| Browser matrix and successful recovery operations | No JavaScript page errors |
| Final successful Compare console check | No console errors and no JavaScript page errors |
| Grafana browser | All 12 panel titles visible; no JavaScript page errors |

Expected HTTP errors during intentional outages were handled as test failures,
not treated as product defects. Existing tests were neither removed nor weakened.
Browser validation used Chromium; this run does **not** claim Safari automation.

## 35. README-only fresh start — PASS

Stopped the identified Vite, Flask, TCP, and UDP processes with SIGINT (the
terminal Ctrl+C signal), then ran `docker compose stop`. Containers exited
normally; the native NetBench listeners were gone. ControlCenter was untouched.
No volumes, configuration, `.venv`, or `node_modules` were deleted.

Restarted using the README's exact five-terminal commands, in order:

1. `docker compose config --quiet`, `docker compose up -d`, `docker compose ps`.
2. Activate `.venv`; `python -m backend.network.tcp_server --host 127.0.0.1`.
3. Activate `.venv`; `python -m backend.network.udp_server --host 127.0.0.1`.
4. Activate `.venv`; set the documented OTLP endpoint; `python -m backend.app`.
5. `npm run dev`; read the printed URL (this run: `http://localhost:5173`).

Verified all five services, direct and proxied HTTP 200 health, browser API
Online, real Compare 1 MB HTTP 200, periodic telemetry reaching Prometheus
(success count 1 per protocol in the new SDK process), Grafana numeric data,
and unchanged old Prometheus history. A further successful Compare checked
browser console errors. Raw fresh-start results are stored separately from the matrix.

## 36–37. README and demo checklist — complete

README now documents observability-first five-terminal startup, Flask's explicit
OTLP endpoint, the actual/dynamic Vite URL, all access URLs, graceful native and
Docker shutdown, and the destructive effect of `down -v`. Architecture includes
the Vite `/api` proxy and separates native application from Docker observability.
The demo checklist covers API Online, Compare 1/10 MB, loss/RTT interpretation,
Prometheus metrics, export delay, Grafana panels, and the telemetry pipeline.
It links these results and clarifies placeholder observability cards.

## 38–40. Remaining limits and scope

- **Loopback only:** all network traffic stayed on this Mac. These numbers are
  local application/loopback measurements, **not Internet, Wi-Fi, or Ethernet
  throughput**. High TCP rates are expected on this path.
- TCP packet loss/retransmissions remain unmeasured (N/A). UDP loss is observed
  DATA-sequence loss and depends on local load/buffers; it was not forced.
- UDP collection/control timing differs from TCP bulk-transfer timing.
- Periodic export and scrape delay visibility; outages can leave gaps. Current
  SDK aggregates reset on Flask restart, while Prometheus retains stored history.
- Frontend observability cards remain placeholders. API Online checks Flask only.
- Vite's proxy is for development; production deployment is outside this phase.
- The existing local Grafana credentials and retained volumes were reused.
- **Two-device LAN testing was not performed or simulated. Phase 11 was not started.**
- **No application containerization, redesign, new feature, or dependency upgrade was added.**

Phase 10 is complete; the application and existing observability stack remain
running for review and demo use.
