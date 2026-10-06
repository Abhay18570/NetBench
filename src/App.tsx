import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import { Activity } from 'lucide-react'
import Navbar from './components/Navbar'
import Dashboard from './pages/Dashboard'
import About from './pages/About'

export default function App() {
  return <BrowserRouter><a className="skip-link" href="#main">Skip to content</a><Navbar /><main id="main" className="main-container"><Routes><Route path="/" element={<Dashboard />} /><Route path="/about" element={<About />} /><Route path="*" element={<section className="page-intro"><div><h1>Page not found</h1><Link to="/">Return to Dashboard</Link></div></section>} /></Routes></main><footer className="site-footer"><span><Activity size={15} />NetBench <span className="footer-divider">/</span> Observable by design.</span><span>TCP / UDP <span className="footer-divider">·</span> LIVE NETWORK TESTS</span></footer></BrowserRouter>
}
