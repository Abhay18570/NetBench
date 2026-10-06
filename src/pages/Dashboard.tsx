import { useEffect, useRef, useState } from 'react'
import { Activity, ArrowUpRight, CheckCircle2, Clock3, FlaskConical, Gauge, LoaderCircle, Radio, Timer, Workflow, Flame, ChartNoAxesCombined } from 'lucide-react'
import TestConfiguration from '../components/TestConfiguration'
import MetricCard from '../components/MetricCard'
import ResultsTable from '../components/ResultsTable'
import { runNetworkTest, apiErrorMessage } from '../services/api'
import type { NetworkTestConfig, NetworkTestResult } from '../types/network'

export default function Dashboard() {
  const [config, setConfig] = useState<NetworkTestConfig>({ serverIp: '127.0.0.1', dataSizeMb: 10, protocol: 'COMPARE' })
  const [result, setResult] = useState<NetworkTestResult | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const active = useRef(false)
  const mounted = useRef(true)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  async function runTest() {
    if (active.current) return
    active.current = true
    setRunning(true)
    setResult(null)
    setError(null)
    try {
      const nextResult = await runNetworkTest(config)
      if (mounted.current) setResult(nextResult)
    } catch (cause) {
      if (mounted.current) setError(apiErrorMessage(cause))
    } finally {
      active.current = false
      if (mounted.current) setRunning(false)
    }
  }
  return <>
    <section className="page-intro"><div><div className="eyebrow"><span className="accent-line" />NETWORK WORKSPACE</div><h1>NetBench<span className="brand-period">.</span></h1><h2>Network Performance Analyzer</h2><p>Analyze and compare TCP and UDP network performance in real time.</p></div><span className="environment-badge"><FlaskConical size={15} />Live Network Test</span></section>
    <div className="demo-notice"><FlaskConical size={17} /><p><strong>A testing ground for your network.</strong> Measurements are generated from actual TCP/UDP socket tests. Localhost results reflect this machine, not internet or Wi-Fi performance.</p><span>LIVE SOCKETS</span></div>
    <TestConfiguration config={config} onChange={(next) => { setConfig(next); setResult(null); setError(null) }} onRun={runTest} running={running} />
    <section className="performance-section" aria-labelledby="performance-title" aria-busy={running}>
      <div className="section-heading"><div><div className="eyebrow">02 / ANALYZE</div><h2 id="performance-title">Performance overview</h2></div><div className={`test-status ${error ? 'failure' : result ? 'success' : ''}`} role="status" aria-live="polite">{running ? <><LoaderCircle size={16} className="spin" />Running Network Test...</> : error ? <>Network Test Failed</> : result ? <><CheckCircle2 size={16} />Test Completed Successfully</> : <><Activity size={16} />Ready for your first test</>}</div></div>
      {error && <div className="error-notice" role="alert"><strong>Network Test Failed</strong><p>{error}</p><p>Start the required TCP server on port 5001 and UDP server on port 5002 before retrying.</p></div>}
      {result && <p className="result-context">Live run · {result.config.serverIp} · {result.config.dataSizeMb} MB · {result.config.protocol === 'COMPARE' ? 'TCP + UDP' : result.config.protocol} · {new Date(result.completedAt).toLocaleTimeString()}</p>}
      <div className="metrics-grid"><MetricCard title="Throughput" unit="Mbps" icon={Gauge} tcp={result?.tcp?.throughputMbps} udp={result?.udp?.throughputMbps} description="Data transferred per second" /><MetricCard title="Application RTT" unit="ms" icon={Clock3} tcp={result?.tcp?.rttMs} udp={result?.udp?.rttMs} description="Application ping/pong round trip" /><MetricCard title="Transfer Time" unit="s" icon={Timer} tcp={result?.tcp?.transferTimeSeconds} udp={result?.udp?.transferTimeSeconds} description="Time to complete the transfer" /><MetricCard title="Packet Loss" unit="%" icon={Radio} tcp={result?.tcp?.packetLossPercent} udp={result?.udp?.packetLossPercent} description="UDP missing packets; TCP N/A" /></div>
      <ResultsTable result={result} protocol={config.protocol} />
    </section>
    <section className="observability" aria-labelledby="observability-title"><div className="section-heading"><div><div className="eyebrow">03 / OBSERVE</div><h2 id="observability-title">Observability</h2></div><span className="subtle-badge">COMING LATER <ArrowUpRight size={12} /></span></div><div className="integration-grid">{[{ name: 'OpenTelemetry', detail: 'Traces & instrumentation', icon: Workflow, color: 'otel' }, { name: 'Prometheus', detail: 'Metrics & monitoring', icon: Flame, color: 'prometheus' }, { name: 'Grafana', detail: 'Dashboards & visualization', icon: ChartNoAxesCombined, color: 'grafana' }].map(({ name, detail, icon: Icon, color }) => <article className="integration-card" key={name}><span className={`integration-icon ${color}`}><Icon size={23} /></span><div><h3>{name}</h3><p>{detail}</p></div><span className="connection-status"><span className="dot" />Not Connected</span></article>)}</div><p className="observability-note">Observability integrations are planned for a later phase.</p></section>
  </>
}
