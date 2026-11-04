# Production transformation

Baseline: `ee75018`. Existing React styling, deterministic workflow, and demo API
are retained. The demo is not a source of production data.

## Audit

The inspected baseline has a process-local ticket store, shared demo policies,
public read endpoints, an operator token for paid AI writes, and frontend mock
fallback. There are no users, organizations, database migrations, mailbox
connections, durable jobs, persisted approvals, or delivery verification.
Analytics include illustrative constants. The Render blueprint explicitly runs
demo mode. Live health/page inspection was attempted but unavailable from this
environment; no hosting state has been changed.

## Milestones

1. Durable workspace foundation: SQLAlchemy/Alembic, PostgreSQL, hashed opaque
   sessions, CSRF, organization roles, invitations, tenant-scoped tickets,
   conversations, knowledge, drafts, audit events, and an authenticated UI.
2. AI and retrieval: validated provider execution, document ingestion, isolated
   retrieval, citations, durable processing, evaluations and failure recovery.
3. Gmail: encrypted OAuth credentials, sync and threading, attachment storage,
   durable send outbox, approval/version checks and provider delivery evidence.
4. Operational acceptance: PostgreSQL integration tests, browser workflows,
   load/restore exercises, staging configuration and controlled release.

Each milestone must report actual tests and outstanding acceptance gates.
No milestone alone establishes production readiness. Provider credentials,
an authorized test mailbox, and approval for test sends are external gates.
