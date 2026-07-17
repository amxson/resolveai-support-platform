export type View = 'dashboard' | 'tickets' | 'new-ticket' | 'ticket' | 'knowledge' | 'analytics'

export interface TicketCreateInput {
  customer_name: string
  customer_email: string
  subject: string
  message: string
  channel: 'Email' | 'Chat' | 'Web Form'
  reference_id?: string
}

export interface AgentStep {
  name: string
  role: string
  status: string
  summary: string
  confidence: number
  duration_ms: number
}

export interface Customer {
  name: string
  email: string
  plan: string
  initials: string
}

export interface KnowledgeMatch {
  article_id: string
  title: string
  excerpt: string
  score: number
  section: string
}

export interface QualityReview {
  status: string
  score: number
  checks: string[]
  notes: string
}

export interface Ticket {
  id: string
  subject: string
  message: string
  customer: Customer
  channel: string
  reference_id?: string | null
  created_at: string
  updated_at: string
  category: string
  priority: string
  sentiment: string
  status: string
  confidence: number
  escalation_needed: boolean
  suggested_next_action: string
  reasoning_summary: string
  knowledge_match: KnowledgeMatch | null
  draft_response: string
  final_response: string
  quality_review: QualityReview | null
  agent_steps: AgentStep[]
  tags: string[]
}

export interface Analytics {
  total_tickets: number
  urgent_tickets: number
  resolved_tickets: number
  average_confidence: number
  resolution_rate: number
  average_first_response_minutes: number
  by_status: Record<string, number>
  by_priority: Record<string, number>
  by_category: Record<string, number>
  weekly_volume: { day: string; tickets: number; resolved: number }[]
}

export interface KnowledgeArticle {
  id: string
  title: string
  category: string
  summary: string
  content: string
  updated_at: string
  usage_count: number
}

