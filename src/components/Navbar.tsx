import { Activity, LayoutDashboard, Info } from 'lucide-react'
import { useEffect, useState } from 'react'
import { checkApiHealth } from '../services/api'
import { NavLink } from 'react-router-dom'

export default function Navbar() {
  const [status, setStatus] = useState<'checking' | 'online' | 'offline'>('checking')
  useEffect(() => {
    const controller = new AbortController()
    async function refresh() {
      try {
        const online = await checkApiHealth(controller.signal)
        if (!controller.signal.aborted) setStatus(online ? 'online' : 'offline')
      } catch {
        if (!controller.signal.aborted) setStatus('offline')
      }
    }
    void refresh()
    const timer = window.setInterval(() => { void refresh() }, 15000)
    return () => { controller.abort(); window.clearInterval(timer) }
  }, [])
  return <header className="navbar">
    <div className="nav-inner">
      <NavLink to="/" className="brand" aria-label="NetBench home">
        <span className="brand-icon"><Activity size={25} /></span>
        <span><strong>NetBench<span className="brand-period">.</span></strong><small>TCP/UDP Network Performance Analyzer</small></span>
      </NavLink>
      <nav aria-label="Main navigation">
        <NavLink to="/" end><LayoutDashboard size={16} />Dashboard</NavLink>
        <NavLink to="/about"><Info size={16} />About</NavLink>
      </nav>
      <div className="system-status"><span>System Status</span><strong className={`api-${status}`} title="Flask API availability only; TCP/UDP servers are checked when a test runs." role="status"><span className="dot" />{status === 'checking' ? 'Checking API…' : status === 'online' ? 'API Online' : 'API Offline'}</strong></div>
    </div>
  </header>
}
