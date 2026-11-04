# Free hosted evaluation release — 2026-11-04

Workspace: https://resolveai-support-platform.vercel.app

API: https://resolveai-support-api.onrender.com

## Hosting and limits

The existing Vercel project remains on Hobby, the existing Render web service
remains Free, and `resolveai-workspace-db` is Neon Free. No paid worker, database,
disk or upgrade was provisioned. The worker shares the API process. Render sleeps
when idle, so background synchronization pauses and the first visit may take
about a minute. The frontend waits for session restoration before showing login.
This is a restricted evaluation deployment, not an always-on service commitment.

Public signup and outbound sending are disabled. The original workspace login
and mailbox grant were preserved when importing the private SQLite snapshot.
Sessions were excluded from the import; hosted users sign in again.
Google's hosted callback is
`https://resolveai-support-platform.vercel.app/api/integrations/gmail/callback`.
The frontend proxies `/api` to Render so Secure, HttpOnly, SameSite=Lax cookies
work on the frontend's own origin. No database or provider keys are built into
the frontend. Server secrets are in Render and the private local settings folder.

## Verified release evidence

- Backend revision `66d6179d2810316688c47acdfe8c67681260c306` deployed on Render;
  `/health` returns workspace mode and `/ready` verifies the migrated database.
- Frontend revision `d247ce3` deployed on Vercel, deployment
  `dpl_7EUAYn5X485d85HmgA1mXEHNRC7v`, with the production alias above.
- [GitHub checks](https://github.com/amxson/resolveai-support-platform/actions/runs/41810364313):
  PostgreSQL suite, browser acceptance, builds, Ruff and dependency audits passed.
  Local backend suite: 37 passed. Local browser suite also passed after adding
  session restoration and attachment upload/download checks.
- Eight hosted acceptance groups passed through the actual Vercel proxy: secure
  login cookies, session restoration/closed signup, tickets/notes/CSRF, tenant
  isolation, encrypted file access, embedded worker/no-policy escalation,
  approval/edit/send-disabled controls, document ingestion and logout. Temporary
  test tenants were removed afterwards; the imported workspace was preserved.
- Dedicated Gmail is connected on the hosted database, scheduled ingestion is
  advancing its saved cursor, and credentials/files decrypt using the private
  server keys. No inbox content or refresh credentials are stored in this repo.

## Live provider limits

Gmail read/synchronization has been observed against the real dedicated mailbox.
The owner declined real test sending, so recipient delivery is intentionally
unverified. Outbound sending stays disabled. Approval, edit invalidation and
the disabled-send rejection passed hosted checks without sending mail.

Live Gemini generation attempts returned HTTP 503 or timed out, including a
lightweight model probe. A successful grounded generation is not claimed.
Provider-double tests verify schema/citation checks and failure handling. The
hosted worker test verifies escalation without a policy; it does not prove model
availability or answer quality. Add actual workspace policies before analyzing
real support conversations. Vector retrieval and formal evaluations remain
outside this release.

## Repeat checks and deploy

Load `DATABASE_URL` from the private deployment configuration into the process
environment. From `backend`, run `python -m production.hosted_check` only against
this evaluation deployment. It creates two isolated temporary tenants, contacts
no real mailbox, makes no AI provider call, and removes only those test records
in a `finally` block. Never point the destructive pytest database fixture at the
hosted database: CI uses its own disposable PostgreSQL service.

Render: root `backend`, build `pip install -r requirements-production.txt`, start
`python -m production.release`, readiness `/ready`. The release entrypoint runs
Alembic before the API and optional embedded worker. Automatic deployment is off;
deploy the reviewed revision manually after its CI checks pass. The feature
branch is `codex/resolveai-production-foundation`; the draft PR remains open.

Vercel: from `frontend`, link the existing `resolveai-support-platform` project
in `amxsons-projects`, then `vercel deploy --prod`. `vercel.json` selects the
workspace build and API proxy. The local `.vercel` link and `.env*` files are
ignored. The CLI's temporary environment file was moved to private local storage.

Keep the last compatible deployment available for rollback. Take a private
database backup before schema changes; application rollback must remain schema
compatible. The initial SQLite backup integrity and imported row counts were
verified, but a managed PostgreSQL restore drill has not yet been completed.
Monitoring/alerts, password recovery, retention controls, complete Gmail change
history, send reconciliation/delivery tracking and load testing remain release
gates for broader customer use. See IMPLEMENTATION-STATUS.md.
