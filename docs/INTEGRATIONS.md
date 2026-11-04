# Gmail + Gemini acceptance setup

These integrations are implemented and tested with controlled HTTP/provider
responses. No live mailbox or Gemini call has been verified in this change.
Use only a dedicated test mailbox until the release gates are closed.

## Gemini

Set server-only `GEMINI_API_KEY` and `GEMINI_MODEL` to a model supported by your
account. Start `python -m production.worker` in backend with the same database
and environment as the API. Queue analysis in a conversation, then refresh it.
Jobs persist across restart, use leases and retry failures three times with
exponential delay. Failed jobs escalate to humans, without fictional fallback.
The worker never overwrites a draft edited after the job was queued.

The pipeline retrieves bounded passages from this workspace's articles using
lexical overlap, requests structured Gemini output, validates its Pydantic schema
and exact citation IDs/quotes, then routes to human review. No matching policy
means escalation without a model call. This baseline is not vector retrieval,
calibrated confidence, or proof that a generated claim is entailed by its quote.
Usage metadata and latency are recorded; cost is null until a verified pricing
configuration is added. Document upload, embeddings and formal evaluations remain.

## Gmail

1. In your Google Cloud project, enable Gmail API. Configure OAuth consent and
   add the dedicated test mailbox as a test user. Public use of restricted Gmail
   scopes may require Google's verification/security assessment.
2. Create a **Web application** OAuth client. Register exactly
   `http://localhost:8000/integrations/gmail/callback` for local testing (or your
   HTTPS API callback for staging). Set `GOOGLE_CLIENT_ID`,
   `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` on the server.
3. Generate an encryption key privately using
   `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
   Store it as `OAUTH_ENCRYPTION_KEY` in the server secret store. Never commit it.
   Rotation accepts a comma-separated list, newest key first; existing rows must
   be re-encrypted/reconnected before dropping an old decryption key.
4. Sign into the workspace and use Integrations → Connect Gmail. The callback
   binds OAuth state to the session's user and organization. Return to the
   workspace after consent; refresh and sign in if needed.
5. Import inbox. This first channel slice imports the **latest 50 inbox messages**,
   groups provider threads, and deduplicates provider IDs. Text-only extraction
   is deliberate; HTML-only messages are marked for original-mailbox inspection.
   Attachments, full-history pagination, scheduled polling and push history
   recovery are still release blockers for a complete channel.
6. Sending defaults closed (`ENABLE_EMAIL_SEND=false`). Only after explicit
   authorization for named test recipients, enable it in the test environment.
   Edit/save/approve a draft, type its recipient, then use the send button.
   The server checks tenant, recipient and exact approved version.

Refresh tokens are encrypted; they never reach the UI. One mailbox identity is
retained per workspace even on disconnect, to prevent old thread IDs being
silently reused against a different account. Disconnect erases the local token;
revoke the app in Google Account permissions if you also want provider revocation.
Use `--no-access-log` on Uvicorn and redact query strings at the proxy, because
OAuth callbacks contain short-lived authorization codes.

A send attempt is durably recorded before I/O. Repeating the same ticket/version
returns the existing outcome. A timeout, process crash or ambiguous response
must be reconciled in Gmail manually; never blindly resend. `accepted` means
Gmail returned an ID, **not recipient delivery**. Delivery verification, bounce
tracking, a send worker/outbox reconciler and complete outbound audit atomicity
are pending. A process crash after provider acceptance can leave `sending`.

## Required live acceptance

Receive a real test email; verify threading/import; add an actual policy; queue
Gemini and inspect its citations; edit/approve; authorize and send a reply; verify
it in both the sender's Sent folder and recipient's inbox; save provider IDs and
audit records with private data redacted. Then test revocation/provider outage.
The automated provider doubles do not satisfy these live acceptance steps.

References: [Gmail server OAuth](https://developers.google.com/workspace/gmail/api/auth/web-server),
[Gmail threading](https://developers.google.com/workspace/gmail/api/guides/threads),
[Gmail sending](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/send),
[Gemini structured output](https://ai.google.dev/gemini-api/docs/generate-content/structured-output).
