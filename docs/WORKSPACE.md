# Authenticated workspace

Working foundation; the full production transformation is still in progress.
The portfolio demo remains `app.main:app`. The independent workspace entrypoint
is `production.app:create_app` and imports no demo data.

## Local run

Create `.venv` at the repository root and install `backend/requirements-production.txt`.
From `backend`, set `DATABASE_URL` and run `alembic upgrade head`, then:

```
python -m uvicorn production.app:create_app --factory --host 127.0.0.1 --port 8000
```

For local development `DATABASE_URL=sqlite:///workspace.db` works. Production
requires PostgreSQL (`postgresql+psycopg://...`), `APP_ENV=production`, HTTPS
`APP_ORIGINS` and secure cookies. Configure database TLS and a trusted proxy.
Schema changes are separate release commands, not automatic API startup work.
Public signup is closed in production unless `ALLOW_SIGNUP=true` explicitly.
Email verification is still required before public registration can be recommended.

In `frontend`, set `VITE_APP_MODE=workspace`,
`VITE_API_BASE_URL=http://localhost:8000`, then `npm ci` and `npm run dev`.
Use consistent hostnames. For hosted use, choose same-site frontend/API domains
or a same-origin reverse proxy; cross-site Vercel/Render defaults will not work
with the SameSite=Lax cookies. Frontend reload requires login again to obtain
a new in-memory CSRF token; no session secrets enter browser storage.

## Implemented security and behavior

Argon2id password hashing; random opaque sessions; only token hashes stored;
12-hour expiry; CSRF protection and explicit CORS; all tenant IDs come from
the authenticated session. Owners/admins manage agents; only owners invite
admins. Membership revocation removes sessions. Owner deletion is refused.
One-use invitations expire after 24 hours and are bound to an email address.
The API returns a private invitation token without pretending to send email.

Tickets, messages, knowledge and audit queries are scoped to organizations.
Draft saving uses atomic version checks; an edit clears approval. Approval
does not send mail. Data mutations and their audit events commit together
before success responses. Authentication limits persist across worker processes.
Responses use no-store, request IDs and safe database errors. Logs omit content
and credentials. This is defense in depth, not a security certification.

## Checks and operations

In backend: `python -m pytest -q`, `ruff check production migrations tests/test_workspace.py`,
`ruff format --check production migrations tests/test_workspace.py`.
Tests migrate disposable SQLite by default. `TEST_DATABASE_URL` runs the same
suite on a disposable PostgreSQL database **downgraded to base after each test**.
Never use a shared/customer database. CI supplies its own PostgreSQL service.
In frontend: `npm run build`, `npm audit`, `npx playwright test`.

`/health` is liveness; `/ready` checks schema/database access. Collect request
logs and configure alerts before release. Before a migration take an encrypted
managed backup or `pg_dump -Fc`. Restore to an isolated database using
`pg_restore`, run readiness plus tenant read/write tests, record the drill.
This restore exercise has not yet been executed. Roll back app images only
to schema-compatible versions; do not downgrade customer data as a shortcut.

## Pending release gates

Gmail/Gemini live acceptance, complete channel synchronization, document
parsing/embeddings/vector retrieval, scheduled mailbox workers, attachments,
retention/deletion, AI evaluations, password recovery, workspace switching,
monitoring/alerts, restore drills and load tests remain. No provider delivery,
production deployment or customer adoption is claimed.

Gmail OAuth, encrypted refresh tokens, bounded manual inbox ingestion and
version-approved send attempts are implemented; see [integration limits and setup](INTEGRATIONS.md).
Gemini execution and durable analysis workers are implemented with provider-double
tests. These tests are not live-provider acceptance or AI quality evaluations.

References: [OWASP sessions](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html),
[OWASP CSRF](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html),
[SQLAlchemy transactions](https://docs.sqlalchemy.org/en/20/orm/session_basics.html).
