import type { LucideIcon } from 'lucide-react'
import ProtocolBadge from './ProtocolBadge'
interface Props { title: string; unit: string; icon: LucideIcon; tcp?: number | null; udp?: number | null; description: string }
export default function MetricCard({ title, unit, icon: Icon, tcp, udp, description }: Props) {
  const digits = unit === 's' ? 4 : 2
  return <article className="metric-card"><div className="metric-heading"><h3>{title}</h3><Icon size={17} /></div><div className="metric-values">{tcp === undefined && udp === undefined ? <div className="empty-metric">—<span>{unit}</span></div> : ([['TCP', tcp], ['UDP', udp]] as const).filter(([, value]) => value !== undefined).map(([protocol, value]) => <div className="metric-value" key={protocol}><ProtocolBadge protocol={protocol} /><strong>{value === null ? 'N/A' : value?.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })}{value !== null && <span>{unit}</span>}</strong></div>)}</div><p>{description}</p></article>
}
