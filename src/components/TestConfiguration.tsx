import { ArrowLeftRight, ArrowRight, ShieldCheck, SlidersHorizontal, Zap, LoaderCircle, Server } from 'lucide-react'
import type { FormEvent } from 'react'
import type { NetworkTestConfig, Protocol } from '../types/network'

const protocols = [
  { value: 'TCP', label: 'TCP', description: 'Reliable Connection', icon: ShieldCheck },
  { value: 'UDP', label: 'UDP', description: 'Fast Connectionless', icon: Zap },
  { value: 'COMPARE', label: 'Compare', description: 'TCP vs UDP', icon: ArrowLeftRight },
] as const

interface Props {
  config: NetworkTestConfig
  onChange: (config: NetworkTestConfig) => void
  onRun: () => void
  running: boolean
}
export default function TestConfiguration({ config, onChange, onRun, running }: Props) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!running) onRun()
  }
  return <section className="panel configuration" aria-labelledby="configuration-title">
    <div className="panel-heading"><div className="heading-icon"><SlidersHorizontal size={18} /></div><div><h2 id="configuration-title">Test Configuration</h2><p>Set up your network performance test.</p></div><span className="step-label">01 / CONFIGURE</span></div>
    <form onSubmit={submit}>
      <fieldset disabled={running} className="config-fields">
        <div className="input-grid">
          <label htmlFor="server-ip">Server IP Address<div className="input-icon"><Server size={17} /><input id="server-ip" required value={config.serverIp} placeholder="127.0.0.1" pattern="((25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])\.){3}(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])" title="Enter a valid IPv4 address, such as 127.0.0.1" onChange={(e) => onChange({ ...config, serverIp: e.target.value })} /></div></label>
          <label htmlFor="data-size">Test Data Size<select id="data-size" value={config.dataSizeMb} onChange={(e) => onChange({ ...config, dataSizeMb: Number(e.target.value) as NetworkTestConfig['dataSizeMb'] })}>{[1, 5, 10, 25, 50].map((size) => <option key={size} value={size}>{size} MB</option>)}</select></label>
        </div>
        <fieldset className="protocol-fieldset"><legend>Protocol</legend><div className="protocol-options">{protocols.map(({ value, label, description, icon: Icon }) => <label className={`protocol-option ${config.protocol === value ? 'selected' : ''}`} key={value}><input type="radio" name="protocol" value={value} checked={config.protocol === value} onChange={() => onChange({ ...config, protocol: value as Protocol })} /><Icon size={21} /><span><strong>{label}</strong><small>{description}</small></span><span className="radio-mark" /></label>)}</div></fieldset>
      </fieldset>
      <div className="config-footer"><p><span className="dot" />Live socket tests <span className="divider">/</span> TCP 5001 / UDP 5002</p><button className="primary-button" disabled={running} type="submit">{running ? <LoaderCircle className="spin" size={17} /> : <ActivityIcon />} {running ? 'Running Network Test...' : 'Start Network Test'}{!running && <ArrowRight size={17} />}</button></div>
    </form>
  </section>
}
function ActivityIcon() { return <Zap size={17} /> }
