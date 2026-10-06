import axios from 'axios'
import type { NetworkTestConfig, NetworkTestResult, ProtocolMetrics, TcpApiResult, UdpApiResult } from '../types/network'

export const api = axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL?.trim() || '/api', timeout: 180_000 })
const body = (config: NetworkTestConfig) => ({ host: config.serverIp, size_mb: config.dataSizeMb })

export async function runTcpTest(config: NetworkTestConfig) {
  return (await api.post<TcpApiResult>('/test/tcp', body(config))).data
}
export async function runUdpTest(config: NetworkTestConfig) {
  return (await api.post<UdpApiResult>('/test/udp', body(config))).data
}
export async function runCompareTest(config: NetworkTestConfig) {
  return (await api.post<{ tcp: TcpApiResult; udp: UdpApiResult }>('/test/compare', body(config))).data
}
function mapMetrics(metrics: TcpApiResult | UdpApiResult): ProtocolMetrics {
  return {
    throughputMbps: metrics.throughput_mbps,
    rttMs: metrics.application_rtt_ms,
    transferTimeSeconds: metrics.transfer_time_seconds,
    packetLossPercent: metrics.packet_loss_percent,
    packetsSent: metrics.protocol === 'UDP' ? metrics.packets_sent : null,
    packetsReceived: metrics.protocol === 'UDP' ? metrics.packets_received : null,
    packetsLost: metrics.protocol === 'UDP' ? metrics.packets_lost : null,
    bytesSent: metrics.protocol === 'UDP' ? metrics.bytes_sent : metrics.bytes_transferred,
    bytesReceived: metrics.protocol === 'UDP' ? metrics.bytes_received : metrics.bytes_transferred,
  }
}
export async function runNetworkTest(config: NetworkTestConfig): Promise<NetworkTestResult> {
  const response = config.protocol === 'COMPARE' ? await runCompareTest(config)
    : config.protocol === 'TCP' ? { tcp: await runTcpTest(config), udp: undefined }
      : { tcp: undefined, udp: await runUdpTest(config) }
  return {
    config: { ...config }, source: 'live', completedAt: new Date().toISOString(),
    tcp: response.tcp ? mapMetrics(response.tcp) : undefined,
    udp: response.udp ? mapMetrics(response.udp) : undefined,
  }
}
export function apiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data
    if (data && typeof data.error === 'string') {
      return `${data.error}.${typeof data.details === 'string' ? ` ${data.details}` : ''}`
    }
    if (error.code === 'ECONNABORTED') return 'The API request timed out. The backend test may still be running; wait before retrying.'
    if (!error.response) return 'Cannot reach the API. Start Flask and check the API URL or Vite proxy connection.'
    return `The API returned HTTP ${error.response.status}. Check that Flask is running and inspect the Vite proxy and Flask logs.`
  }
  return 'Could not complete the network test. Check the API and test-server logs.'
}
export async function checkApiHealth(signal: AbortSignal): Promise<boolean> {
  const { data } = await api.get('/health', { timeout: 3000, signal })
  return data.status === 'ok' && data.service === 'NetBench API'
}
