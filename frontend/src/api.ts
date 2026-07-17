import { mockAnalytics, mockKnowledge, mockTickets } from './mockData'
import type { Analytics, KnowledgeArticle, Ticket, TicketCreateInput } from './types'

const apiBase = (
  import.meta.env.VITE_API_BASE_URL || (import.meta.env.DEV ? 'http://localhost:8000' : '')
).replace(/\/$/, '')

async function request<T>(path: string, options?: RequestInit, timeoutMs = 2500): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, { ...options, signal: AbortSignal.timeout(timeoutMs) })
  if (!response.ok) throw new Error(`API request failed with ${response.status}`)
  return response.json() as Promise<T>
}

export async function createTicket(payload: TicketCreateInput): Promise<Ticket> {
  if (!apiBase) throw new Error('The demo API is not configured for this deployment.')
  return request<Ticket>('/tickets', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }, 60_000)
}

export async function loadPlatformData(): Promise<{
  tickets: Ticket[]
  analytics: Analytics
  knowledge: KnowledgeArticle[]
  source: 'api' | 'demo'
}> {
  if (!apiBase) {
    return { tickets: mockTickets, analytics: mockAnalytics, knowledge: mockKnowledge, source: 'demo' }
  }

  try {
    const [ticketData, analytics, knowledge] = await Promise.all([
      request<{ items: Ticket[] }>('/tickets'),
      request<Analytics>('/analytics'),
      request<KnowledgeArticle[]>('/knowledge-base'),
    ])
    return { tickets: ticketData.items, analytics, knowledge, source: 'api' }
  } catch {
    return { tickets: mockTickets, analytics: mockAnalytics, knowledge: mockKnowledge, source: 'demo' }
  }
}
