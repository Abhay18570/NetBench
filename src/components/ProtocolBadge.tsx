export default function ProtocolBadge({ protocol }: { protocol: 'TCP' | 'UDP' }) {
  return <span className={`protocol-badge ${protocol.toLowerCase()}`}><span className="dot" />{protocol}</span>
}
