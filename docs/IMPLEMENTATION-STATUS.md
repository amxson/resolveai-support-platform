# Production transformation status

## Implemented

- Separate authenticated workspace preserving the original demo and palette.
- Persistent organizations, memberships, invitations, tickets, messages, notes,
  knowledge articles, audit records, analysis jobs and send attempts.
- PostgreSQL migrations, tenant-scoped authorization, sessions/CSRF, Argon2id,
  authentication rate limits, role enforcement and session revocation.
- Versioned human draft approval, assignment/status, team and knowledge controls.
- Structured Gemini adapter with citations, bounded lexical retrieval, usage and
  latency records; durable job leases, retries and failure escalation.
- Gmail OAuth, encrypted refresh credentials and key rotation support, bounded
  resumable paginated inbox import, scheduled polling/backoff, thread/dedup handling
  and approved-version sends.
- No automatic retry of uncertain sends; new incoming messages invalidate approval.
- Encrypted tenant-scoped file upload/download/deletion and bounded PDF/TXT/Markdown
  knowledge ingestion, plus safe supported Gmail attachments.
- Session restoration across page reload, a same-origin Vercel API proxy and a
  free Render release entrypoint with an embedded worker.
- Docker/Caddy/PostgreSQL composition template and setup/operational documentation.

## Verified by automated tests

The backend suite covers tenant attacks, role denials, expired sessions, CSRF,
invitation replay, revocation, restart persistence, optimistic draft conflicts,
provider/citation failures, worker crash limits, OAuth state isolation,
duplicate import, paginated restart recovery, revoked grants, encrypted file isolation,
approved sending and uncertain-send protection. Provider tests
use controlled doubles; they do not contact Google or send actual mail.

Browser acceptance covers signup → ticket → internal note → saved draft → approval
→ audit → logout. Width checks: 390, 768, 1440. Frontend production build, Ruff,
npm vulnerability audit and a disposable PostgreSQL CI job are included.
See PR checks for the latest revision's exact results, including dependency audit.

## External acceptance gates

Configure the dedicated Gmail OAuth client/consent and Gemini server credentials
privately using `.env.workspace.example`. No secret should be pasted into chat.
Authorize specific test sends only after inspecting the intended recipient and
draft. Verify provider IDs and actual inbox delivery; Gmail acceptance alone is
insufficient. The dedicated mailbox is connected; real inbox import and encrypted
attachment ingestion were observed locally. The free Neon database was created
and the private workspace snapshot imported with all row counts verified.
Gemini live generation returned busy responses/timeouts, so it is not passed.
The restricted free evaluation deployment is live on Vercel + Render + Neon.
Eight hosted acceptance groups passed through the real frontend proxy; temporary
test tenants were removed. See [release evidence and limitations](HOSTED-RELEASE.md).
Docker is absent locally; its template has not been executed.

## Outstanding engineering gates

This change is **not the complete production product**. Remaining work includes
complete Gmail change-history/push recovery and embedding/vector retrieval,
finer document permissions,
retention/deletion, verified email/password recovery, workspace switching/settings,
formal AI evaluations, cost calculation, distributed usage limits, send-worker
reconciliation, delivery/bounce tracking, monitoring/alerts, secret-scanning CI,
backup restoration drills, load testing and release/rollback verification.
The send path's external I/O and audit commit are not fully atomic; a durable
attempt makes uncertainty visible but reconciliation is required after a crash.

Do not merge/release this draft as though all original acceptance criteria passed.
No customer usage, accuracy percentages, provider availability or security
certification is claimed.
