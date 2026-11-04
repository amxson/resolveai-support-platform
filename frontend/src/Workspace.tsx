import { useState, type FormEvent } from 'react'
import './workspace.css'

type Ticket = { id: string; subject: string; customer_email: string; status: string; draft: string; draft_version: number; approved_version: number | null; assignee_id: string | null }
type Message = { id: string; kind: string; body: string }
type Member = { id: string; email: string; role: string }
type Article = { id: string; title: string; content: string; version: number }
const base = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')

export default function Workspace() {
  const [csrf, setCsrf] = useState('')
  const [identity, setIdentity] = useState<{ email: string; role: string; organization: string } | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [signup, setSignup] = useState(false)
  const [view, setView] = useState('inbox')
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [selected, setSelected] = useState<Ticket | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [draft, setDraft] = useState('')
  const [analysis, setAnalysis] = useState<{ id: string; status: string; error: string | null; result: Record<string, unknown> }[]>([])
  const [members, setMembers] = useState<Member[]>([])
  const [articles, setArticles] = useState<Article[]>([])
  const [audit, setAudit] = useState<{ id: string; action: string; resource_id: string; created_at: number }[]>([])
  const [invitation, setInvitation] = useState('')
  const [mailbox, setMailbox] = useState<{ email: string | null; status: string } | null>(null)
  const [delivery, setDelivery] = useState('')
  const [counts, setCounts] = useState<Record<string, number>>({})
  async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
    const response = await fetch(`${base}${path}`, { method, credentials: 'include', signal: AbortSignal.timeout(15000),
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: body === undefined ? undefined : JSON.stringify(body) })
    if (!response.ok) {
      if (response.status === 401) setIdentity(null)
      const result = await response.json().catch(() => ({}))
      throw new Error(typeof result.detail === 'string' ? result.detail : `Request failed (${response.status})`)
    }
    return response.status === 204 ? undefined as T : response.json() as Promise<T>
  }
  async function run(action: () => Promise<void>) {
    setBusy(true); setError('')
    try { await action() } catch (e) { setError(e instanceof Error ? e.message : 'Request failed') } finally { setBusy(false) }
  }
  async function refresh() {
    const [queue, team, knowledge, history, analytics] = await Promise.all([
      api<Ticket[]>('/tickets'), api<Member[]>('/team'), api<Article[]>('/knowledge'),
      api<typeof audit>('/audit'), api<{ by_status: Record<string, number> }>('/analytics'),
    ])
    setTickets(queue); setMembers(team); setArticles(knowledge); setAudit(history); setCounts(analytics.by_status)
  }
  async function open(ticket: Ticket) {
    const detail = await api<{ ticket: Ticket; messages: Message[] }>(`/tickets/${ticket.id}`)
    setSelected(detail.ticket); setMessages(detail.messages); setDraft(detail.ticket.draft)
    setAnalysis(await api(`/tickets/${ticket.id}/analysis`))
  }
  function values(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    return Object.fromEntries(new FormData(event.currentTarget)) as Record<string, string>
  }
  const canAdmin = identity?.role === 'admin' || identity?.role === 'owner'
  if (!identity) return <main className="workspace auth-page"><form className="panel workspace-form" onSubmit={event => {
    const data = values(event)
    void run(async () => {
      const result = await api<{ csrf_token: string }>(data.token ? '/invitations/accept' : signup ? '/auth/signup' : '/auth/login', 'POST', data)
      setCsrf(result.csrf_token)
      setSignup(false)
      setIdentity(await api('/auth/me'))
      await refresh()
    })
  }}>
    <span className="eyebrow">ResolveAI · Workspace</span><h1>{signup ? 'Create your workspace' : 'Sign in'}</h1>
    <p>Persistent support records. This application contains no sample customers.</p>
    <label>Email<input name="email" type="email" autoComplete="username" required /></label>
    <label>Password<input name="password" type="password" minLength={12} maxLength={128} autoComplete={signup ? 'new-password' : 'current-password'} required /></label>
    {signup && <label>Workspace name<input name="organization" minLength={2} maxLength={120} required /></label>}
    <label>Invitation token (if invited)<input name="token" autoComplete="off" /></label>
    {error && <p role="alert">{error}</p>}
    <button className="primary-button" disabled={busy}>{busy ? 'Working…' : signup ? 'Create workspace' : 'Sign in / accept invitation'}</button>
    <button type="button" className="secondary-button" onClick={() => setSignup(!signup)}>{signup ? 'Use existing account' : 'Create an account'}</button>
  </form></main>
  return <div className="workspace app-shell">
    <aside className="sidebar"><div className="brand-row"><div><div className="brand-name">ResolveAI</div><small>{identity.organization}</small></div></div>
      <nav className="nav-list" aria-label="Workspace">{['inbox', 'knowledge', 'team', 'integrations', 'activity'].map(item => <button key={item} className={`nav-item ${view === item ? 'active' : ''}`} onClick={() => setView(item)}>{item}</button>)}</nav>
      <div className="sidebar-user"><span><strong>{identity.email}</strong><small>{identity.role}</small></span></div>
      <button disabled={busy} onClick={() => void run(async () => { await api('/auth/logout', 'POST'); setIdentity(null); setCsrf(''); setTickets([]); setSelected(null) })}>Sign out</button>
    </aside>
    <main className="main-content"><header className="page-header"><div><span className="eyebrow">Support workspace</span><h1>{view}</h1><p>Review the conversation and policy evidence before approving a response. Sending requires a separate action and a connected mailbox.</p></div><button className="secondary-button" disabled={busy} onClick={() => void run(refresh)}>Refresh</button></header>
      {error && <div className="prototype-note" role="alert">{error}<button onClick={() => setError('')}>Dismiss</button></div>}
      <div className="page-content">
      {view === 'inbox' && <>
        <section className="metrics-grid">{Object.entries(counts).map(([status, count]) => <div className="metric-card" key={status}><div className="metric-copy"><span>{status}</span><strong>{count}</strong></div></div>)}</section>
        <section className="panel workspace-form"><h2>Create ticket</h2><form onSubmit={event => { const data = values(event); const form = event.currentTarget; void run(async () => { const ticket = await api<Ticket>('/tickets', 'POST', data); form.reset(); await refresh(); await open(ticket) }) }}>
          <label>Subject<input name="subject" minLength={3} maxLength={200} required /></label><label>Customer email<input name="customer_email" type="email" required /></label><label>Message<textarea name="message" maxLength={20000} required /></label><button className="primary-button" disabled={busy}>Create ticket</button>
        </form></section>
        <section className="panel workspace-form"><h2>Conversation inbox</h2><form onSubmit={event => { const data = values(event); void run(async () => setTickets(await api(`/tickets?q=${encodeURIComponent(data.q)}`))) }}><label>Search subject<input name="q" maxLength={200} /></label><button disabled={busy}>Search</button></form>
          {tickets.length === 0 && <p>No tickets found.</p>}{tickets.map(ticket => <button className="workspace-ticket" key={ticket.id} onClick={() => void run(() => open(ticket))}><strong>{ticket.subject}</strong><span>{ticket.customer_email} · {ticket.status}</span></button>)}
        </section>
        {selected && <section className="panel workspace-form"><h2>{selected.subject}</h2>{messages.map(message => <article className="workspace-message" key={message.id}><small>{message.kind}</small><p>{message.body}</p></article>)}
          <form key={`${selected.id}:${selected.status}`} onSubmit={event => { const data = values(event); void run(async () => { await api(`/tickets/${selected.id}`, 'PATCH', { status: data.status, assignee_id: data.assignee_id || null }); await open(selected); await refresh() }) }}><label>Status<select name="status" defaultValue={selected.status}>{['open', 'in_review', 'escalated', 'resolved'].map(s => <option key={s}>{s}</option>)}</select></label><label>Assigned to<select name="assignee_id" defaultValue={selected.assignee_id || ''}><option value="">Unassigned</option>{members.map(m => <option key={m.id} value={m.id}>{m.email}</option>)}</select></label><button disabled={busy}>Save status and assignment</button></form>
          <form onSubmit={event => { const data = values(event); const form = event.currentTarget; void run(async () => { await api(`/tickets/${selected.id}/notes`, 'POST', data); form.reset(); await open(selected); await refresh() }) }}><label>Internal note<textarea name="body" required maxLength={20000} /></label><button disabled={busy}>Add note</button></form>
          <div className="workspace-actions"><button disabled={busy} onClick={() => void run(async () => { await api(`/tickets/${selected.id}/analyze`, 'POST'); await open(selected) })}>Queue Gemini analysis</button><button disabled={busy} onClick={() => void run(() => open(selected))}>Refresh conversation and analysis</button></div>
          {analysis.map(job => <details key={job.id}><summary>Analysis: {job.status}{job.error ? ` · ${job.error}` : ''}</summary><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify(job.result, null, 2)}</pre></details>)}
          <label>Response draft<textarea aria-label="Response draft" value={draft} onChange={e => setDraft(e.target.value)} maxLength={20000} /></label>
          <div className="workspace-actions"><button disabled={busy || !draft} onClick={() => void run(async () => { await api(`/tickets/${selected.id}/draft`, 'PUT', { body: draft, version: selected.draft_version }); await open(selected); await refresh() })}>Save draft</button>
          <button disabled={busy || !selected.draft || draft !== selected.draft} onClick={() => void run(async () => { await api(`/tickets/${selected.id}/approve`, 'POST', { version: selected.draft_version }); await open(selected); await refresh() })}>Approve saved draft</button>
          <button disabled={busy || selected.approved_version === null} onClick={() => void run(async () => { await api(`/tickets/${selected.id}/reject`, 'POST'); await open(selected); await refresh() })}>Reject approval</button></div>
          <p>{selected.approved_version === null ? 'Awaiting review' : `Version ${selected.approved_version} approved. Email not sent.`}</p>
          {selected.approved_version !== null && <form onSubmit={event => { const data = values(event); void run(async () => { const result = await api<{ status: string; provider_id?: string }>(`/tickets/${selected.id}/send`, 'POST', { version: selected.approved_version, recipient: data.recipient }); setDelivery(`${result.status}${result.provider_id ? ` · provider reference ${result.provider_id}` : ''}`); await refresh() }) }}><label>Confirm recipient before sending<input name="recipient" type="email" placeholder={selected.customer_email} required /></label><button disabled={busy}>Send approved response through Gmail</button>{delivery && <p role="status">{delivery}. Provider acceptance is not proof of recipient delivery.</p>}</form>}
        </section>}
      </>}
      {view === 'knowledge' && <section className="panel workspace-form"><h2>Workspace knowledge</h2>{canAdmin && <form onSubmit={event => { const data = values(event); const form = event.currentTarget; void run(async () => { await api('/knowledge', 'POST', data); form.reset(); await refresh() }) }}><label>Title<input name="title" minLength={2} maxLength={200} required /></label><label>Policy text<textarea name="content" maxLength={100000} required /></label><button disabled={busy}>Add article</button></form>}{articles.map(article => <article key={article.id}><h3>{article.title} · v{article.version}</h3><p>{article.content}</p>{canAdmin && <button disabled={busy} onClick={() => void run(async () => { await api(`/knowledge/${article.id}`, 'DELETE'); await refresh() })}>Delete article</button>}</article>)}</section>}
      {view === 'team' && <section className="panel workspace-form"><h2>Team</h2>{members.map(member => <p key={member.id}>{member.email} · {member.role}{canAdmin && member.role === 'agent' && <button disabled={busy} onClick={() => void run(async () => { await api(`/team/${member.id}`, 'DELETE'); await refresh() })}>Remove access</button>}</p>)}{canAdmin && <form onSubmit={event => { const data = values(event); void run(async () => { const result = await api<{ token: string }>('/invitations', 'POST', data); setInvitation(result.token); await refresh() }) }}><label>Invite email<input name="email" type="email" required /></label><label>Role<select name="role"><option>agent</option>{identity.role === 'owner' && <option>admin</option>}</select></label><button disabled={busy}>Create invitation</button></form>}{invitation && <p>Share this token privately (valid 24 hours): <code>{invitation}</code>. No email was sent.</p>}</section>}
      {view === 'activity' && <section className="panel workspace-form"><h2>Audit history</h2>{audit.map(event => <p key={event.id}><time>{new Date(event.created_at * 1000).toLocaleString()}</time> · {event.action} · {event.resource_id}</p>)}</section>}
      {view === 'integrations' && <section className="panel workspace-form"><h2>Gmail connection</h2>{canAdmin ? <><p>Connect a dedicated support mailbox. Import currently covers the latest 50 inbox messages as plain text. Attachments and full-history synchronization are pending.</p><div className="workspace-actions"><button disabled={busy} onClick={() => void run(async () => { const result = await api<{ url: string }>('/integrations/gmail/connect', 'POST'); const url = new URL(result.url); if (url.origin !== 'https://accounts.google.com') throw new Error('Unexpected authorization URL'); window.location.assign(url.href) })}>Connect / reconnect Gmail</button><button disabled={busy} onClick={() => void run(async () => setMailbox(await api('/integrations/gmail')))}>Check connection</button><button disabled={busy} onClick={() => void run(async () => { await api('/integrations/gmail/sync', 'POST'); await refresh(); setMailbox(await api('/integrations/gmail')) })}>Import inbox</button><button disabled={busy} onClick={() => void run(async () => { await api('/integrations/gmail', 'DELETE'); setMailbox(await api('/integrations/gmail')) })}>Disconnect Gmail</button></div>{mailbox && <p>{mailbox.email || 'No mailbox'} · {mailbox.status}</p>}<p>Sending is disabled until the operator explicitly enables outbound email. An uncertain send requires manual inspection of Gmail; it is never retried automatically.</p></> : <p>An administrator manages mailbox connections.</p>}</section>}
      </div>
    </main>
  </div>
}
