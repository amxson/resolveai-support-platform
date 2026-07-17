import { useEffect, useMemo, useState } from 'react'
import {
  Activity, AlertTriangle, ArrowLeft, ArrowRight, BarChart3, BookOpen, Bot,
  Check, CheckCircle2, ChevronDown, CircleDot, Clock3, Copy, Filter, Gauge,
  Headphones, Inbox, LayoutDashboard, Menu, MessageSquareText, MoreHorizontal,
  Search, Send, ShieldCheck, Sparkles, Target, TicketCheck, TrendingUp, UserRound,
  Users, WandSparkles, X, Zap,
} from 'lucide-react'
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { loadPlatformData } from './api'
import { mockAnalytics, mockKnowledge, mockTickets } from './mockData'
import type { Analytics, KnowledgeArticle, Ticket, View } from './types'

const CHART_COLORS = ['#2f7d68', '#d7a94e', '#667872', '#c96e57', '#9bb8ae', '#d9dfda']

const viewTitles: Record<View, { eyebrow: string; title: string; description: string }> = {
  dashboard: { eyebrow: 'Operations overview', title: 'Support operations', description: 'Monitor the fictional demo queue and multi-agent workflow.' },
  tickets: { eyebrow: 'Ticket workspace', title: 'Support inbox', description: 'Review, filter, and inspect AI-assisted demo tickets.' },
  ticket: { eyebrow: 'Ticket analysis', title: 'Ticket intelligence', description: 'Inspect the workflow evidence before a human sends the response.' },
  knowledge: { eyebrow: 'Reference library', title: 'Knowledge base', description: 'Fictional policy articles used by the retrieval workflow.' },
  analytics: { eyebrow: 'Workflow reporting', title: 'Analytics', description: 'Explore demonstration metrics and support workflow patterns.' },
}

function getInitialRoute(): { view: View; ticketId?: string } {
  const route = window.location.hash.replace(/^#\/?/, '')
  if (route.startsWith('tickets/')) return { view: 'ticket', ticketId: route.split('/')[1] }
  if (['dashboard', 'tickets', 'knowledge', 'analytics'].includes(route)) return { view: route as View }
  return { view: 'dashboard' }
}

function priorityClass(value: string) {
  return `pill pill-${value.toLowerCase().replace(' ', '-')}`
}

function statusClass(value: string) {
  return `pill status-${value.toLowerCase().replace(' ', '-')}`
}

function timeLabel(date: string) {
  const hours = Math.max(1, Math.round((new Date('2026-07-16T10:00:00+03:00').getTime() - new Date(date).getTime()) / 3_600_000))
  return hours < 24 ? `${hours}h ago` : `${Math.round(hours / 24)}d ago`
}

function Avatar({ ticket, small = false }: { ticket: Ticket; small?: boolean }) {
  const palette = ['avatar-sage', 'avatar-sand', 'avatar-blue', 'avatar-rose']
  const index = ticket.customer.name.charCodeAt(0) % palette.length
  return <div className={`avatar ${palette[index]} ${small ? 'avatar-small' : ''}`}>{ticket.customer.initials}</div>
}

function Sidebar({ view, navigate, mobileOpen, close }: { view: View; navigate: (view: View, ticketId?: string) => void; mobileOpen: boolean; close: () => void }) {
  const nav = [
    { id: 'dashboard' as View, label: 'Overview', icon: LayoutDashboard },
    { id: 'tickets' as View, label: 'Ticket inbox', icon: Inbox, count: 6 },
    { id: 'knowledge' as View, label: 'Knowledge base', icon: BookOpen },
    { id: 'analytics' as View, label: 'Analytics', icon: BarChart3 },
  ]
  return (
    <>
      <aside className={`sidebar ${mobileOpen ? 'sidebar-open' : ''}`}>
        <div className="brand-row">
          <div className="brand-mark"><span /><CircleDot size={18} /></div>
          <div><div className="brand-name">ResolveAI</div><div className="brand-subtitle">Support Platform</div></div>
          <button className="sidebar-close" onClick={close} aria-label="Close navigation"><X size={20} /></button>
        </div>
        <div className="demo-badge"><Sparkles size={14} /><span><strong>Portfolio prototype</strong><small>Fictional demo workspace</small></span></div>
        <nav className="nav-list" aria-label="Primary navigation">
          <span className="nav-label">Workspace</span>
          {nav.map((item) => {
            const Icon = item.icon
            const active = view === item.id || (view === 'ticket' && item.id === 'tickets')
            return (
              <button key={item.id} className={`nav-item ${active ? 'active' : ''}`} onClick={() => { navigate(item.id); close() }}>
                <Icon size={18} /><span>{item.label}</span>{item.count && <em>{item.count}</em>}
              </button>
            )
          })}
        </nav>
        <div className="workflow-mini">
          <div className="workflow-mini-head"><span>Agent workflow</span><strong>5 active</strong></div>
          <div className="agent-orbit">
            <div className="orbit-core"><Bot size={18} /></div>
            {[0, 1, 2, 3, 4].map((n) => <i key={n} style={{ transform: `rotate(${n * 72}deg) translateY(-27px)` }} />)}
          </div>
          <p>Five specialized stages collaborate, with a human approval checkpoint.</p>
        </div>
        <div className="sidebar-user">
          <div className="user-avatar">AM</div><span><strong>Alex Morgan</strong><small>Demo operator</small></span><MoreHorizontal size={18} />
        </div>
      </aside>
      {mobileOpen && <button className="sidebar-overlay" onClick={close} aria-label="Close navigation overlay" />}
    </>
  )
}

function Header({ view, source, onMenu }: { view: View; source: 'api' | 'demo'; onMenu: () => void }) {
  const copy = viewTitles[view]
  return (
    <header className="page-header">
      <div className="header-title">
        <button className="mobile-menu" onClick={onMenu} aria-label="Open navigation"><Menu size={20} /></button>
        <div><span className="eyebrow">{copy.eyebrow}</span><h1>{copy.title}</h1><p>{copy.description}</p></div>
      </div>
      <div className="header-actions">
        <div className="engine-status"><i /><span>{source === 'api' ? 'Demo API connected' : 'Local demo dataset'}</span></div>
        <button className="icon-button" aria-label="Open notifications"><Activity size={19} /><b>2</b></button>
        <div className="header-avatar">AM</div>
      </div>
    </header>
  )
}

function MetricCard({ label, value, detail, icon: Icon, tone, trend }: { label: string; value: string | number; detail: string; icon: typeof Inbox; tone: string; trend?: string }) {
  return (
    <div className="metric-card">
      <div className={`metric-icon ${tone}`}><Icon size={20} /></div>
      <div className="metric-copy"><span>{label}</span><strong>{value}</strong></div>
      {trend && <div className="trend"><TrendingUp size={13} />{trend}</div>}
      <p>{detail}</p>
    </div>
  )
}

function TicketTable({ tickets, navigate, compact = false }: { tickets: Ticket[]; navigate: (view: View, ticketId?: string) => void; compact?: boolean }) {
  return (
    <div className={`table-wrap ${compact ? 'compact-table' : ''}`}>
      <table>
        <thead><tr><th>Customer</th><th>Issue</th><th>Priority</th><th>Status</th><th>AI confidence</th><th>Updated</th><th /></tr></thead>
        <tbody>
          {tickets.map((ticket) => (
            <tr key={ticket.id} onClick={() => navigate('ticket', ticket.id)}>
              <td><div className="customer-cell"><Avatar ticket={ticket} small /><span><strong>{ticket.customer.name}</strong><small>{ticket.id}</small></span></div></td>
              <td><div className="issue-cell"><strong>{ticket.subject}</strong><span>{ticket.category}</span></div></td>
              <td><span className={priorityClass(ticket.priority)}><i />{ticket.priority}</span></td>
              <td><span className={statusClass(ticket.status)}>{ticket.status}</span></td>
              <td><div className="confidence-cell"><strong>{ticket.confidence}%</strong><span><i style={{ width: `${ticket.confidence}%` }} /></span></div></td>
              <td className="muted-cell">{timeLabel(ticket.updated_at)}</td>
              <td><button className="row-arrow" aria-label={`Open ${ticket.id}`}><ArrowRight size={16} /></button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Dashboard({ tickets, analytics, navigate }: { tickets: Ticket[]; analytics: Analytics; navigate: (view: View, ticketId?: string) => void }) {
  const categoryData = Object.entries(analytics.by_category).map(([name, value]) => ({ name, value }))
  return (
    <div className="page-content dashboard-page">
      <section className="prototype-note"><div><ShieldCheck size={18} /><span><strong>Demonstration environment</strong>All tickets, customers, policies, and performance metrics are fictional portfolio data.</span></div><span className="mode-chip">Demo mode</span></section>
      <section className="metrics-grid">
        <MetricCard label="Tickets in demo" value={analytics.total_tickets} detail="Fictional seeded cases" icon={Inbox} tone="sage" trend="12% sample lift" />
        <MetricCard label="High impact" value={analytics.urgent_tickets} detail="High or urgent priority" icon={AlertTriangle} tone="amber" />
        <MetricCard label="Resolved" value={analytics.resolved_tickets} detail={`${analytics.resolution_rate}% demo resolution rate`} icon={TicketCheck} tone="blue" trend="8% sample lift" />
        <MetricCard label="Avg. confidence" value={`${analytics.average_confidence}%`} detail="Across completed analyses" icon={Gauge} tone="slate" />
      </section>
      <section className="dashboard-grid">
        <div className="panel volume-panel">
          <div className="panel-head"><div><span className="section-kicker">Demo volume</span><h2>Ticket flow</h2><p>Sample weekly activity used to demonstrate analytics.</p></div><button className="select-button">Last 7 days <ChevronDown size={15} /></button></div>
          <div className="chart-shell">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={analytics.weekly_volume} margin={{ top: 10, right: 8, left: -20, bottom: 0 }}>
                <defs><linearGradient id="ticketFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#2f7d68" stopOpacity={0.28} /><stop offset="100%" stopColor="#2f7d68" stopOpacity={0} /></linearGradient></defs>
                <CartesianGrid stroke="#e7ebe8" vertical={false} />
                <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fill: '#7b8984', fontSize: 12 }} />
                <YAxis axisLine={false} tickLine={false} tick={{ fill: '#7b8984', fontSize: 12 }} />
                <Tooltip contentStyle={{ border: '0', borderRadius: 12, boxShadow: '0 10px 30px rgba(16,38,32,.12)', fontSize: 12 }} />
                <Area type="monotone" dataKey="tickets" stroke="#2f7d68" strokeWidth={2.5} fill="url(#ticketFill)" />
                <Area type="monotone" dataKey="resolved" stroke="#d7a94e" strokeWidth={2} fill="transparent" strokeDasharray="5 4" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="chart-legend"><span><i className="legend-sage" />Tickets</span><span><i className="legend-gold" />Resolved</span><small>Illustrative metrics</small></div>
        </div>
        <div className="panel category-panel">
          <div className="panel-head"><div><span className="section-kicker">Classification</span><h2>Issue mix</h2></div><button className="icon-plain"><MoreHorizontal size={19} /></button></div>
          <div className="donut-wrap">
            <ResponsiveContainer width="100%" height={178}>
              <PieChart><Pie data={categoryData} dataKey="value" innerRadius={52} outerRadius={73} paddingAngle={4} stroke="none">{categoryData.map((_, index) => <Cell key={index} fill={CHART_COLORS[index % CHART_COLORS.length]} />)}</Pie><Tooltip /></PieChart>
            </ResponsiveContainer>
            <div className="donut-center"><strong>{analytics.total_tickets}</strong><span>tickets</span></div>
          </div>
          <div className="category-list">{categoryData.slice(0, 4).map((item, index) => <div key={item.name}><span><i style={{ background: CHART_COLORS[index] }} />{item.name}</span><strong>{item.value}</strong></div>)}</div>
        </div>
      </section>
      <section className="dashboard-lower">
        <div className="panel recent-panel">
          <div className="panel-head"><div><span className="section-kicker">Live demo queue</span><h2>Recent tickets</h2></div><button className="text-button" onClick={() => navigate('tickets')}>View inbox <ArrowRight size={15} /></button></div>
          <TicketTable tickets={tickets.slice(0, 4)} navigate={navigate} compact />
        </div>
        <div className="panel agents-panel">
          <div className="panel-head"><div><span className="section-kicker">CrewAI concept</span><h2>Workflow stages</h2></div><span className="live-chip"><i />Ready</span></div>
          <div className="agent-list">
            {[
              ['Triage Agent', 'Classify & prioritize', Target], ['Knowledge Agent', 'Retrieve guidance', BookOpen],
              ['Response Writer', 'Draft reply', MessageSquareText], ['Quality Review', 'Check & refine', ShieldCheck],
              ['Decision Agent', 'Route next action', Zap],
            ].map(([name, detail, Icon], index) => {
              const IconComponent = Icon as typeof Target
              return <div className="agent-row" key={String(name)}><div className="agent-step-icon"><IconComponent size={16} /></div><span><strong>{String(name)}</strong><small>{String(detail)}</small></span><em>{index + 1}</em></div>
            })}
          </div>
          <div className="human-check"><UserRound size={16} /><span><strong>Human-in-the-loop</strong>Review remains required before sending.</span></div>
        </div>
      </section>
    </div>
  )
}

function TicketsPage({ tickets, navigate }: { tickets: Ticket[]; navigate: (view: View, ticketId?: string) => void }) {
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('All statuses')
  const [priority, setPriority] = useState('All priorities')
  const filtered = tickets.filter((ticket) => {
    const matchesSearch = `${ticket.id} ${ticket.subject} ${ticket.customer.name} ${ticket.category}`.toLowerCase().includes(search.toLowerCase())
    return matchesSearch && (status === 'All statuses' || ticket.status === status) && (priority === 'All priorities' || ticket.priority === priority)
  })
  return (
    <div className="page-content">
      <section className="inbox-stats">
        {['All tickets', 'Needs review', 'Escalated', 'Resolved'].map((item, index) => <button key={item} className={index === 0 ? 'active' : ''}><span>{item}</span><strong>{[tickets.length, tickets.filter(t => t.status === 'In Review').length, tickets.filter(t => t.status === 'Escalated').length, tickets.filter(t => t.status === 'Resolved').length][index]}</strong></button>)}
      </section>
      <section className="panel inbox-panel">
        <div className="inbox-toolbar">
          <div className="search-box"><Search size={17} /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search customer, ticket, or issue…" aria-label="Search tickets" /></div>
          <div className="filter-group">
            <label><Filter size={16} /><select value={status} onChange={(e) => setStatus(e.target.value)}><option>All statuses</option><option>New</option><option>In Review</option><option>Escalated</option><option>Resolved</option></select></label>
            <label><select value={priority} onChange={(e) => setPriority(e.target.value)}><option>All priorities</option><option>Low</option><option>Medium</option><option>High</option><option>Urgent</option></select></label>
          </div>
        </div>
        <div className="inbox-result-line"><span>{filtered.length} demo tickets</span><small>Sorted by most recent</small></div>
        {filtered.length ? <TicketTable tickets={filtered} navigate={navigate} /> : <div className="empty-state"><Search size={30} /><h3>No tickets match</h3><p>Try clearing one of the filters.</p></div>}
      </section>
    </div>
  )
}

function InfoCard({ label, value, icon: Icon, children }: { label: string; value: string; icon: typeof Target; children?: React.ReactNode }) {
  return <div className="info-card"><div className="info-card-icon"><Icon size={17} /></div><div><span>{label}</span><strong>{value}</strong>{children}</div></div>
}

function TicketDetail({ ticket, navigate }: { ticket: Ticket; navigate: (view: View, ticketId?: string) => void }) {
  const [copied, setCopied] = useState(false)
  const copyReply = async () => {
    await navigator.clipboard?.writeText(ticket.final_response)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1800)
  }
  return (
    <div className="page-content ticket-detail-page">
      <div className="detail-topline">
        <button className="back-button" onClick={() => navigate('tickets')}><ArrowLeft size={17} /> Back to inbox</button>
        <div className="detail-top-actions"><span className={statusClass(ticket.status)}>{ticket.status}</span><button className="secondary-button"><MoreHorizontal size={17} /> More</button><button className="primary-button"><Send size={16} /> Approve draft</button></div>
      </div>
      <section className="ticket-hero">
        <div><div className="ticket-id-line"><span>{ticket.id}</span><span>•</span><span>{ticket.channel}</span><span>•</span><span>{timeLabel(ticket.created_at)}</span></div><h2>{ticket.subject}</h2><p>AI-assisted analysis generated from fictional ticket and policy data.</p></div>
        <div className="confidence-ring" style={{ '--score': `${ticket.confidence * 3.6}deg` } as React.CSSProperties}><div><strong>{ticket.confidence}%</strong><span>confidence</span></div></div>
      </section>
      <div className="detail-layout">
        <main className="detail-main">
          <section className="panel message-panel">
            <div className="panel-head"><div><span className="section-kicker">Original message</span><h2>Customer request</h2></div><span className="channel-chip"><MessageSquareText size={14} />{ticket.channel}</span></div>
            <div className="message-author"><Avatar ticket={ticket} /><span><strong>{ticket.customer.name}</strong><small>{ticket.customer.email}</small></span><time>{new Date(ticket.created_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</time></div>
            <blockquote>{ticket.message}</blockquote>
          </section>
          <section className="analysis-block">
            <div className="section-heading"><div><span className="section-kicker">Triage result</span><h2>AI analysis</h2></div><span className="analysis-complete"><CheckCircle2 size={15} />5 stages complete</span></div>
            <div className="info-grid">
              <InfoCard label="Category" value={ticket.category} icon={Target} />
              <InfoCard label="Priority" value={ticket.priority} icon={AlertTriangle}><span className={priorityClass(ticket.priority)}><i />{ticket.priority}</span></InfoCard>
              <InfoCard label="Sentiment" value={ticket.sentiment} icon={Activity} />
              <InfoCard label="Routing" value={ticket.escalation_needed ? 'Escalation advised' : 'Standard review'} icon={Users} />
            </div>
            <div className="reasoning-card"><div className="reasoning-head"><WandSparkles size={17} /><strong>Reasoning summary</strong><span>Concise rationale</span></div><p>{ticket.reasoning_summary}</p></div>
          </section>
          {ticket.knowledge_match && <section className="panel knowledge-match-panel">
            <div className="panel-head"><div><span className="section-kicker">Knowledge retrieval</span><h2>Matched guidance</h2></div><div className="match-score"><strong>{ticket.knowledge_match.score}%</strong><span>match</span></div></div>
            <div className="knowledge-match-body"><div className="kb-icon"><BookOpen size={19} /></div><div><span>{ticket.knowledge_match.article_id} · {ticket.knowledge_match.section}</span><h3>{ticket.knowledge_match.title}</h3><p>{ticket.knowledge_match.excerpt}</p><button onClick={() => navigate('knowledge')}>Open knowledge base <ArrowRight size={14} /></button></div></div>
          </section>}
          <section className="panel response-panel">
            <div className="panel-head"><div><span className="section-kicker">Suggested reply</span><h2>Quality-reviewed response</h2></div><div className="response-actions"><span className="approved-chip"><ShieldCheck size={14} />Approved</span><button onClick={copyReply}>{copied ? <Check size={15} /> : <Copy size={15} />}{copied ? 'Copied' : 'Copy'}</button></div></div>
            <div className="response-copy">{ticket.final_response.split('\n').map((line, index) => line ? <p key={index}>{line}</p> : <br key={index} />)}</div>
            {ticket.quality_review && <div className="qa-footer"><div className="qa-score"><ShieldCheck size={19} /><span><strong>{ticket.quality_review.score}/100 quality score</strong><small>{ticket.quality_review.status}</small></span></div><div className="qa-checks">{ticket.quality_review.checks.map((check) => <span key={check}><Check size={12} />{check}</span>)}</div></div>}
          </section>
        </main>
        <aside className="detail-aside">
          <section className="panel customer-panel">
            <div className="aside-heading"><span>Customer</span><button><MoreHorizontal size={17} /></button></div>
            <div className="profile"><Avatar ticket={ticket} /><div><strong>{ticket.customer.name}</strong><span>{ticket.customer.email}</span></div></div>
            <dl><div><dt>Plan</dt><dd>{ticket.customer.plan}</dd></div><div><dt>Channel</dt><dd>{ticket.channel}</dd></div><div><dt>Previous tickets</dt><dd>3 demo cases</dd></div></dl>
          </section>
          <section className="next-action-card"><div><Zap size={18} /><span>Suggested next action</span></div><p>{ticket.suggested_next_action}</p><button><UserRound size={15} />Assign for review</button></section>
          <section className="panel timeline-panel">
            <div className="aside-heading"><span>Agent activity</span><small>1.9s demo run</small></div>
            <div className="timeline">{ticket.agent_steps.map((step, index) => <div className="timeline-step" key={step.name}><div className="timeline-dot"><Check size={11} /></div><div><strong>{step.name}</strong><span>{step.role}</span><p>{step.summary}</p><small>{step.confidence}% confidence · {step.duration_ms}ms</small></div>{index < ticket.agent_steps.length - 1 && <i />}</div>)}</div>
          </section>
        </aside>
      </div>
    </div>
  )
}

function KnowledgePage({ knowledge }: { knowledge: KnowledgeArticle[] }) {
  const [search, setSearch] = useState('')
  const filtered = knowledge.filter(article => `${article.title} ${article.category} ${article.summary}`.toLowerCase().includes(search.toLowerCase()))
  return (
    <div className="page-content">
      <section className="knowledge-hero">
        <div><span className="section-kicker light">Retrieval source</span><h2>Policy knowledge, made traceable.</h2><p>Six fictional articles ground the prototype workflow and make every suggested response easier to inspect.</p></div>
        <div className="knowledge-hero-stat"><BookOpen size={22} /><span><strong>{knowledge.length}</strong>demo articles</span></div>
      </section>
      <section className="kb-toolbar"><div className="search-box"><Search size={17} /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search the demo knowledge base…" /></div><button className="secondary-button"><Filter size={15} />All categories</button></section>
      <section className="kb-grid">{filtered.map((article, index) => <article className="kb-card" key={article.id}>
        <div className="kb-card-top"><div className={`kb-file-icon kb-tone-${index % 3}`}><BookOpen size={18} /></div><span>{article.id}</span><button><MoreHorizontal size={17} /></button></div>
        <span className="category-label">{article.category}</span><h3>{article.title}</h3><p>{article.summary}</p>
        <div className="kb-preview">{article.content}</div>
        <footer><span><Clock3 size={13} />Updated {article.updated_at}</span><span><Activity size={13} />Used {article.usage_count}×</span></footer>
      </article>)}</section>
      <p className="data-footnote"><ShieldCheck size={14} />This library is sample content created for the portfolio prototype; it does not represent any company’s policies.</p>
    </div>
  )
}

function AnalyticsPage({ analytics }: { analytics: Analytics }) {
  const priorityData = Object.entries(analytics.by_priority).map(([name, value]) => ({ name, value }))
  const categoryData = Object.entries(analytics.by_category).map(([name, value]) => ({ name: name.replace(' Question', '').replace(' Issue', ''), value }))
  return (
    <div className="page-content analytics-page">
      <section className="metrics-grid analytics-metrics">
        <MetricCard label="Demo resolution rate" value={`${analytics.resolution_rate}%`} detail="3 of 6 fictional tickets" icon={TicketCheck} tone="sage" trend="Illustrative" />
        <MetricCard label="First response" value={`${analytics.average_first_response_minutes}m`} detail="Simulated average" icon={Clock3} tone="blue" />
        <MetricCard label="AI confidence" value={`${analytics.average_confidence}%`} detail="Average demo analysis" icon={Gauge} tone="slate" />
        <MetricCard label="Policy coverage" value="100%" detail="Tickets with a KB match" icon={BookOpen} tone="amber" />
      </section>
      <section className="analytics-grid">
        <div className="panel weekly-panel">
          <div className="panel-head"><div><span className="section-kicker">Illustrative trend</span><h2>Resolution volume</h2><p>Demonstration data across one sample week.</p></div><button className="select-button">Last 7 days <ChevronDown size={15} /></button></div>
          <div className="analytics-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={analytics.weekly_volume} barGap={4} margin={{ left: -22, right: 4 }}><CartesianGrid stroke="#e7ebe8" vertical={false} /><XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fill: '#7b8984', fontSize: 12 }} /><YAxis axisLine={false} tickLine={false} tick={{ fill: '#7b8984', fontSize: 12 }} /><Tooltip cursor={{ fill: '#f3f6f4' }} contentStyle={{ border: 0, borderRadius: 12, boxShadow: '0 10px 30px rgba(16,38,32,.12)' }} /><Bar dataKey="tickets" fill="#d9e4df" radius={[5, 5, 0, 0]} /><Bar dataKey="resolved" fill="#2f7d68" radius={[5, 5, 0, 0]} /></BarChart></ResponsiveContainer></div>
          <div className="chart-legend"><span><i style={{ background: '#d9e4df' }} />Received</span><span><i className="legend-sage" />Resolved</span></div>
        </div>
        <div className="panel priority-panel">
          <div className="panel-head"><div><span className="section-kicker">Queue health</span><h2>Priority mix</h2></div></div>
          <div className="priority-donut"><ResponsiveContainer width="100%" height={210}><PieChart><Pie data={priorityData} dataKey="value" innerRadius={62} outerRadius={84} paddingAngle={5} stroke="none">{priorityData.map((_, index) => <Cell key={index} fill={['#9bb8ae', '#d7a94e', '#c96e57', '#8f4f43'][index]} />)}</Pie><Tooltip /></PieChart></ResponsiveContainer><div><strong>{analytics.total_tickets}</strong><span>total</span></div></div>
          <div className="priority-legend">{priorityData.map((item, index) => <span key={item.name}><i style={{ background: ['#9bb8ae', '#d7a94e', '#c96e57', '#8f4f43'][index] }} />{item.name}<strong>{item.value}</strong></span>)}</div>
        </div>
      </section>
      <section className="analytics-lower">
        <div className="panel category-bars">
          <div className="panel-head"><div><span className="section-kicker">Routing patterns</span><h2>Tickets by category</h2></div></div>
          <div className="horizontal-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={categoryData} layout="vertical" margin={{ left: 8, right: 24 }}><XAxis type="number" hide domain={[0, 2]} /><YAxis type="category" dataKey="name" width={86} axisLine={false} tickLine={false} tick={{ fill: '#56635f', fontSize: 12 }} /><Tooltip cursor={{ fill: '#f6f8f6' }} /><Bar dataKey="value" fill="#2f7d68" barSize={12} radius={[0, 6, 6, 0]} /></BarChart></ResponsiveContainer></div>
        </div>
        <div className="panel performance-panel">
          <div className="panel-head"><div><span className="section-kicker">Stage performance</span><h2>Agent workflow quality</h2></div><span className="mode-chip">Demo run</span></div>
          <div className="performance-table"><div className="performance-head"><span>Stage</span><span>Confidence</span><span>Latency</span></div>{[
            ['Triage & sentiment', '94%', '420ms'], ['Knowledge retrieval', '96%', '310ms'], ['Response drafting', '91%', '680ms'], ['Quality review', '97%', '360ms'], ['Decision routing', '93%', '240ms'],
          ].map(([stage, confidence, latency]) => <div key={stage}><span><i />{stage}</span><strong>{confidence}</strong><em>{latency}</em></div>)}</div>
        </div>
      </section>
      <p className="data-footnote"><BarChart3 size={14} />Analytics are illustrative and derived from fictional sample records—not production performance.</p>
    </div>
  )
}

function LoadingScreen() {
  return <div className="loading-screen"><div className="loading-mark"><Bot size={26} /></div><strong>Preparing support operations</strong><span>Loading the demonstration workspace…</span></div>
}

export default function App() {
  const initial = getInitialRoute()
  const [view, setView] = useState<View>(initial.view)
  const [ticketId, setTicketId] = useState(initial.ticketId || 'TICK-1042')
  const [tickets, setTickets] = useState<Ticket[]>(mockTickets)
  const [analytics, setAnalytics] = useState<Analytics>(mockAnalytics)
  const [knowledge, setKnowledge] = useState<KnowledgeArticle[]>(mockKnowledge)
  const [source, setSource] = useState<'api' | 'demo'>('demo')
  const [loading, setLoading] = useState(true)
  const [mobileOpen, setMobileOpen] = useState(false)

  useEffect(() => {
    loadPlatformData().then((data) => {
      setTickets(data.tickets); setAnalytics(data.analytics); setKnowledge(data.knowledge); setSource(data.source); setLoading(false)
    })
  }, [])

  useEffect(() => {
    const handleHash = () => {
      const route = getInitialRoute(); setView(route.view); if (route.ticketId) setTicketId(route.ticketId)
    }
    window.addEventListener('hashchange', handleHash)
    return () => window.removeEventListener('hashchange', handleHash)
  }, [])

  const navigate = (next: View, id?: string) => {
    if (next === 'ticket') {
      const selected = id || ticketId
      setTicketId(selected); window.location.hash = `/tickets/${selected}`
    } else {
      window.location.hash = `/${next}`
    }
    setView(next)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const selectedTicket = useMemo(() => tickets.find((ticket) => ticket.id === ticketId) || tickets[0], [tickets, ticketId])

  if (loading) return <LoadingScreen />

  return (
    <div className="app-shell">
      <Sidebar view={view} navigate={navigate} mobileOpen={mobileOpen} close={() => setMobileOpen(false)} />
      <div className="main-shell">
        <Header view={view} source={source} onMenu={() => setMobileOpen(true)} />
        {view === 'dashboard' && <Dashboard tickets={tickets} analytics={analytics} navigate={navigate} />}
        {view === 'tickets' && <TicketsPage tickets={tickets} navigate={navigate} />}
        {view === 'ticket' && selectedTicket && <TicketDetail ticket={selectedTicket} navigate={navigate} />}
        {view === 'knowledge' && <KnowledgePage knowledge={knowledge} />}
        {view === 'analytics' && <AnalyticsPage analytics={analytics} />}
      </div>
    </div>
  )
}

