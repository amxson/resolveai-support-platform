import type { Analytics, KnowledgeArticle, Ticket } from './types'

const agentSteps = (category: string, priority: string, sentiment: string, article: string) => [
  {
    name: 'Triage Agent', role: 'Classification & urgency', status: 'Completed',
    summary: `Classified as ${category}; ${priority.toLowerCase()} priority with ${sentiment.toLowerCase()} sentiment.`,
    confidence: 94, duration_ms: 420,
  },
  {
    name: 'Knowledge Base Agent', role: 'Policy retrieval', status: 'Completed',
    summary: `Matched ${article} against the fictional demo policy library.`,
    confidence: 96, duration_ms: 310,
  },
  {
    name: 'Response Writer Agent', role: 'Reply drafting', status: 'Completed',
    summary: 'Drafted a policy-grounded response with a clear customer next step.',
    confidence: 91, duration_ms: 680,
  },
  {
    name: 'Quality Review Agent', role: 'Safety & tone review', status: 'Completed',
    summary: 'Checked empathy, policy alignment, unsupported promises, and action clarity.',
    confidence: 97, duration_ms: 360,
  },
  {
    name: 'Decision Agent', role: 'Routing & final action', status: 'Completed',
    summary: priority === 'Urgent' || priority === 'High' ? 'Recommended a specialist handoff before sending.' : 'Recommended human approval before sending.',
    confidence: 93, duration_ms: 240,
  },
]

const commonReview = {
  status: 'Approved with safeguards',
  score: 97,
  checks: ['Tone and empathy', 'Knowledge-base alignment', 'No unsupported promise', 'Clear next action'],
  notes: 'The prototype review found no policy conflicts and retained a human approval step.',
}

export const mockTickets: Ticket[] = [
  {
    id: 'TICK-1042', subject: 'Delivery is six days late',
    message: 'My order was due six days ago and tracking has not moved since Monday. I need it for an event this weekend. Please tell me where it is or refund me.',
    customer: { name: 'Maya Thompson', email: 'maya.thompson@example.com', plan: 'Growth', initials: 'MT' },
    channel: 'Email', created_at: '2026-07-16T08:42:00+03:00', updated_at: '2026-07-16T08:43:00+03:00',
    category: 'Delivery Issue', priority: 'High', sentiment: 'Frustrated', status: 'Escalated', confidence: 94,
    escalation_needed: true, suggested_next_action: 'Route to shipping operations for human review before sending',
    reasoning_summary: 'The delivery is more than five business days late and tracking is stalled. Timing raises the business impact, while the message shows understandable frustration. KB-001 supplies the closest demo-policy guidance.',
    knowledge_match: { article_id: 'KB-001', title: 'Delivery delays and carrier escalation', excerpt: 'Steps for delayed shipments, stalled tracking, and carrier checks.', score: 97, section: 'Delivery Issue' },
    draft_response: 'Hi Maya,\n\nI’m sorry your delivery is late and that tracking has stopped updating. We’ll check the stalled tracking with the carrier and review the order with our shipping team. I’ve flagged this for specialist review before any reply is sent.\n\nBest,\nSupport team',
    final_response: 'Hi Maya,\n\nI’m sorry your delivery is now six days late and that tracking has stopped updating. We’ll check the shipment with the carrier and route the order to our shipping team for review. We won’t promise a new delivery date until the carrier check is complete, but the ticket will remain escalated while the location and next option are confirmed.\n\nBest,\nSupport team',
    quality_review: commonReview, agent_steps: agentSteps('Delivery Issue', 'High', 'Frustrated', 'KB-001'), tags: ['Delivery Issue', 'Frustrated', 'Demo data'],
  },
  {
    id: 'TICK-1039', subject: 'Password reset email never arrives',
    message: 'I have tried the password reset three times but the email never arrives. I am locked out and need access before my client call today.',
    customer: { name: 'Daniel Kim', email: 'daniel.kim@example.com', plan: 'Business', initials: 'DK' },
    channel: 'Web', created_at: '2026-07-16T07:18:00+03:00', updated_at: '2026-07-16T07:19:00+03:00',
    category: 'Account Access', priority: 'Urgent', sentiment: 'Frustrated', status: 'In Review', confidence: 95,
    escalation_needed: true, suggested_next_action: 'Route to account security for human review before sending',
    reasoning_summary: 'Repeated failed reset attempts and a time-sensitive lockout indicate an urgent account-access issue. The workflow avoids requesting passwords or security codes.',
    knowledge_match: { article_id: 'KB-003', title: 'Account recovery and reset troubleshooting', excerpt: 'Safe reset steps and escalation triggers for locked accounts.', score: 98, section: 'Account Access' },
    draft_response: 'Hi Daniel,\n\nI’m sorry the reset emails have not reached you and that you’re locked out. Please check spam or junk, confirm you’re using the account email, wait ten minutes, and try once more.\n\nBest,\nSupport team',
    final_response: 'Hi Daniel,\n\nI’m sorry the password reset emails still haven’t arrived. Please check spam or junk, confirm you’re using the email linked to the account, and wait ten minutes before one final attempt. I’ve also flagged the lockout for secure account review. For your protection, please don’t send a password or verification code in your reply.\n\nBest,\nSupport team',
    quality_review: commonReview, agent_steps: agentSteps('Account Access', 'Urgent', 'Frustrated', 'KB-003'), tags: ['Account Access', 'Frustrated', 'Demo data'],
  },
  {
    id: 'TICK-1037', subject: 'Refund for unopened headset',
    message: 'I ordered the wrong headset last week. It is still sealed in the box. Can I return it for a refund to my original card?',
    customer: { name: 'Sofia Martinez', email: 'sofia.martinez@example.com', plan: 'Starter', initials: 'SM' },
    channel: 'Email', created_at: '2026-07-15T16:05:00+03:00', updated_at: '2026-07-15T16:08:00+03:00',
    category: 'Refund Request', priority: 'Medium', sentiment: 'Neutral', status: 'Resolved', confidence: 96,
    escalation_needed: false, suggested_next_action: 'Send the reviewed reply and keep the ticket available for follow-up',
    reasoning_summary: 'The item is unopened and was ordered recently, which aligns with the fictional 30-day demo refund policy.',
    knowledge_match: { article_id: 'KB-002', title: 'Refund eligibility and payment routing', excerpt: 'Eligibility rules for unopened items and original payment refunds.', score: 98, section: 'Refund Request' },
    draft_response: 'Hi Sofia,\n\nThe sealed headset appears eligible for refund review. Please share the order number.\n\nBest,\nSupport team',
    final_response: 'Hi Sofia,\n\nI can help with the return. Because the headset is still sealed and was ordered last week, it appears eligible for review under the unopened-item policy. Please reply with the order number so the return can be checked and, if approved, routed back to the original payment method.\n\nBest,\nSupport team',
    quality_review: commonReview, agent_steps: agentSteps('Refund Request', 'Medium', 'Neutral', 'KB-002'), tags: ['Refund Request', 'Neutral', 'Demo data'],
  },
  {
    id: 'TICK-1032', subject: 'Question about team pricing',
    message: 'We are a team of 12 and are comparing plans. Does the Business tier include priority support and consolidated billing?',
    customer: { name: 'Noah Williams', email: 'noah.williams@example.com', plan: 'Starter', initials: 'NW' },
    channel: 'Chat', created_at: '2026-07-15T11:31:00+03:00', updated_at: '2026-07-15T11:34:00+03:00',
    category: 'Pricing Question', priority: 'Low', sentiment: 'Neutral', status: 'Resolved', confidence: 93,
    escalation_needed: false, suggested_next_action: 'Send the reviewed reply and keep the ticket available for follow-up',
    reasoning_summary: 'The ticket asks for plan capabilities rather than reporting a service failure. A sales handoff avoids inventing commercial terms.',
    knowledge_match: { article_id: 'KB-006', title: 'Plans, pricing, and sales handoff', excerpt: 'Guidance for plan comparisons without inventing commercial terms.', score: 96, section: 'Pricing Question' },
    draft_response: 'Hi Noah,\n\nThanks for considering the Business plan. A specialist can confirm the current terms for 12 seats.\n\nBest,\nSupport team',
    final_response: 'Hi Noah,\n\nThanks for considering the Business plan for your team. Priority support and consolidated billing depend on the current plan configuration, so I’d recommend a sales handoff to confirm the exact terms for 12 seats without quoting unverified details.\n\nBest,\nSupport team',
    quality_review: commonReview, agent_steps: agentSteps('Pricing Question', 'Low', 'Neutral', 'KB-006'), tags: ['Pricing Question', 'Neutral', 'Demo data'],
  },
  {
    id: 'TICK-1028', subject: 'Checkout fails after payment',
    message: 'Checkout shows an error after I submit payment, but my card now has two pending charges. This is the third time it has happened and I am very frustrated.',
    customer: { name: 'Aisha Patel', email: 'aisha.patel@example.com', plan: 'Growth', initials: 'AP' },
    channel: 'Web', created_at: '2026-07-14T14:22:00+03:00', updated_at: '2026-07-14T14:24:00+03:00',
    category: 'Technical Bug', priority: 'High', sentiment: 'Negative', status: 'Escalated', confidence: 97,
    escalation_needed: true, suggested_next_action: 'Route to engineering and billing for human review before sending',
    reasoning_summary: 'Repeated checkout failures plus duplicate pending charges indicate a technical and financial-impact issue requiring specialist review.',
    knowledge_match: { article_id: 'KB-004', title: 'Duplicate charges and checkout errors', excerpt: 'Billing-safe response guidance for checkout and duplicate-charge reports.', score: 98, section: 'Technical Bug' },
    draft_response: 'Hi Aisha,\n\nI’m sorry checkout failed and left duplicate pending charges. Please do not retry payment while we review this.\n\nBest,\nSupport team',
    final_response: 'Hi Aisha,\n\nI’m sorry checkout has failed repeatedly and left two pending charges. Please don’t retry payment while the review is active. I’ve flagged the checkout error for engineering and both pending charges for billing review. The ticket won’t be marked resolved until the payment state is verified.\n\nBest,\nSupport team',
    quality_review: commonReview, agent_steps: agentSteps('Technical Bug', 'High', 'Negative', 'KB-004'), tags: ['Technical Bug', 'Negative', 'Demo data'],
  },
  {
    id: 'TICK-1024', subject: 'Damaged blender in delivery',
    message: 'The blender arrived cracked and the box was crushed. I am disappointed and need a safe replacement, not another damaged unit.',
    customer: { name: 'Ethan Brooks', email: 'ethan.brooks@example.com', plan: 'Starter', initials: 'EB' },
    channel: 'Email', created_at: '2026-07-14T09:09:00+03:00', updated_at: '2026-07-14T09:12:00+03:00',
    category: 'Damaged Product', priority: 'Medium', sentiment: 'Frustrated', status: 'Resolved', confidence: 95,
    escalation_needed: false, suggested_next_action: 'Send the reviewed reply and keep the ticket available for follow-up',
    reasoning_summary: 'The message clearly reports damaged goods and asks for a safe replacement. Evidence and packaging guidance apply.',
    knowledge_match: { article_id: 'KB-005', title: 'Damaged product replacement workflow', excerpt: 'Evidence, packaging, and replacement guidance for damaged goods.', score: 97, section: 'Damaged Product' },
    draft_response: 'Hi Ethan,\n\nI’m sorry the blender arrived damaged. Please keep the packaging and send photos so replacement options can be reviewed.\n\nBest,\nSupport team',
    final_response: 'Hi Ethan,\n\nI’m sorry the blender arrived cracked. Please keep the product and packaging, and send photos of the damage and crushed box if you haven’t already. Once the damage is confirmed, the ticket can be reviewed for a safe replacement or refund.\n\nBest,\nSupport team',
    quality_review: commonReview, agent_steps: agentSteps('Damaged Product', 'Medium', 'Frustrated', 'KB-005'), tags: ['Damaged Product', 'Frustrated', 'Demo data'],
  },
]

export const mockKnowledge: KnowledgeArticle[] = [
  { id: 'KB-001', title: 'Delivery delays and carrier escalation', category: 'Delivery Issue', summary: 'Steps for delayed shipments, stalled tracking, and carrier checks.', content: 'When tracking has not updated for more than three business days, offer a carrier check. Escalate orders more than five business days late.', updated_at: 'Jul 12, 2026', usage_count: 84 },
  { id: 'KB-002', title: 'Refund eligibility and payment routing', category: 'Refund Request', summary: 'Eligibility rules for unopened items and original payment refunds.', content: 'Unopened items can usually be refunded within 30 days. Confirm the order number and route approved refunds to the original method.', updated_at: 'Jul 10, 2026', usage_count: 61 },
  { id: 'KB-003', title: 'Account recovery and reset troubleshooting', category: 'Account Access', summary: 'Safe reset steps and escalation triggers for locked accounts.', content: 'Ask the customer to check spam, wait ten minutes, and retry with the account email. Escalate when reset emails never arrive.', updated_at: 'Jul 8, 2026', usage_count: 73 },
  { id: 'KB-004', title: 'Duplicate charges and checkout errors', category: 'Technical Bug', summary: 'Billing-safe response guidance for checkout and duplicate-charge reports.', content: 'Collect the order reference and route duplicate charges to billing. Do not promise a reversal time or ask the customer to repeat payment.', updated_at: 'Jul 7, 2026', usage_count: 49 },
  { id: 'KB-005', title: 'Damaged product replacement workflow', category: 'Damaged Product', summary: 'Evidence, packaging, and replacement guidance for damaged goods.', content: 'Ask the customer to keep packaging and provide photos. Offer replacement or refund after damage is confirmed.', updated_at: 'Jul 4, 2026', usage_count: 37 },
  { id: 'KB-006', title: 'Plans, pricing, and sales handoff', category: 'Pricing Question', summary: 'Guidance for plan comparisons without inventing commercial terms.', content: 'Answer only from approved plan information and offer a sales handoff for exact pricing, discounts, or contracts.', updated_at: 'Jul 2, 2026', usage_count: 28 },
]

export const mockAnalytics: Analytics = {
  total_tickets: 6, urgent_tickets: 3, resolved_tickets: 3, average_confidence: 95,
  resolution_rate: 50, average_first_response_minutes: 4,
  by_status: { New: 0, 'In Review': 1, Escalated: 2, Resolved: 3 },
  by_priority: { Low: 1, Medium: 2, High: 2, Urgent: 1 },
  by_category: { 'Delivery Issue': 1, 'Account Access': 1, 'Refund Request': 1, 'Pricing Question': 1, 'Technical Bug': 1, 'Damaged Product': 1 },
  weekly_volume: [
    { day: 'Mon', tickets: 14, resolved: 10 }, { day: 'Tue', tickets: 19, resolved: 15 },
    { day: 'Wed', tickets: 17, resolved: 14 }, { day: 'Thu', tickets: 24, resolved: 18 },
    { day: 'Fri', tickets: 21, resolved: 17 }, { day: 'Sat', tickets: 11, resolved: 9 },
    { day: 'Sun', tickets: 8, resolved: 7 },
  ],
}

