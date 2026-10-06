import { ArrowLeftRight } from 'lucide-react'
import type { NetworkTestResult, Protocol, ProtocolMetrics } from '../types/network'
import ProtocolBadge from './ProtocolBadge'
const rows: { label: string; key: keyof ProtocolMetrics; unit: string; digits: number }[] = [
  { label: 'Throughput', key: 'throughputMbps', unit: ' Mbps', digits: 2 },
  { label: 'Application RTT', key: 'rttMs', unit: ' ms', digits: 2 },
  { label: 'Transfer Time', key: 'transferTimeSeconds', unit: ' s', digits: 4 },
  { label: 'Bytes Sent', key: 'bytesSent', unit: '', digits: 0 },
  { label: 'Bytes Received', key: 'bytesReceived', unit: '', digits: 0 },
  { label: 'Packets Sent', key: 'packetsSent', unit: '', digits: 0 },
  { label: 'Packets Received', key: 'packetsReceived', unit: '', digits: 0 },
  { label: 'Packets Lost', key: 'packetsLost', unit: '', digits: 0 },
  { label: 'Packet Loss', key: 'packetLossPercent', unit: '%', digits: 2 },
]
export default function ResultsTable({ result, protocol }: { result: NetworkTestResult | null; protocol: Protocol }) {
  const columns = (['TCP', 'UDP'] as const).filter((item) => protocol === 'COMPARE' || protocol === item)
  function value(metrics: ProtocolMetrics | undefined, row: typeof rows[number]) {
    if (!metrics) return '—'
    const number = metrics[row.key]
    return number === null ? 'N/A' : `${number.toLocaleString('en-US', { minimumFractionDigits: row.digits, maximumFractionDigits: row.digits })}${row.unit}`
  }
  return <section className="panel results-panel" aria-labelledby="results-title"><div className="panel-heading"><div className="heading-icon"><ArrowLeftRight size={18} /></div><div><h2 id="results-title">{protocol === 'COMPARE' ? 'TCP vs UDP Comparison' : `${protocol} Results`}</h2><p>Measurements from actual socket tests.</p></div><span className="subtle-badge">LIVE TEST</span></div><div className="table-scroll"><table><thead><tr><th scope="col">Metric</th>{columns.map((item) => <th scope="col" key={item}><ProtocolBadge protocol={item} /></th>)}</tr></thead><tbody>{rows.map((row) => <tr key={row.key}><th scope="row">{row.label}</th>{columns.map((item) => <td key={item}>{value(item === 'TCP' ? result?.tcp : result?.udp, row)}</td>)}</tr>)}</tbody></table></div><div className="table-note">TCP packet statistics and IP packet loss are not measured (N/A). UDP throughput is receiver goodput; its elapsed time includes a 150 ms reorder window and control exchanges. Application RTT is not ICMP latency.</div></section>
}
