export type Protocol = 'TCP' | 'UDP' | 'COMPARE'
export interface NetworkTestConfig {
  serverIp: string
  dataSizeMb: 1 | 5 | 10 | 25 | 50
  protocol: Protocol
}
export interface ProtocolMetrics {
  throughputMbps: number
  rttMs: number
  transferTimeSeconds: number
  packetsSent: number | null
  packetsReceived: number | null
  packetsLost: number | null
  packetLossPercent: number | null
  bytesSent: number
  bytesReceived: number
}
export interface NetworkTestResult {
  config: NetworkTestConfig
  completedAt: string
  source: 'live'
  tcp?: ProtocolMetrics
  udp?: ProtocolMetrics
}
interface ApiMetrics {
  host: string
  port: number
  test_size_mb: number
  throughput_mbps: number
  application_rtt_ms: number
  transfer_time_seconds: number
}
export interface TcpApiResult extends ApiMetrics {
  protocol: 'TCP'
  bytes_transferred: number
  packet_loss_percent: null
}
export interface UdpApiResult extends ApiMetrics {
  protocol: 'UDP'
  bytes_sent: number
  bytes_received: number
  packets_sent: number
  packets_received: number
  packets_lost: number
  packet_loss_percent: number
}
