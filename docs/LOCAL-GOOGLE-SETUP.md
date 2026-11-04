# Dedicated Gmail + Gemini setup

Use the existing Google Cloud project `resolveai-513701` if that is the project
you intend to keep for this test. This guide does not activate billing, send mail
or publish the OAuth app. Do not use real customer data during free-tier testing.

## Google Cloud

1. Google Auth Platform → Get started: name `ResolveAI Local Test`, choose your
   support email; audience **External** for a regular Gmail account; enter the
   developer contact email, review terms and create the configuration.
2. Audience: keep publishing status **Testing**, add the dedicated Gmail account
   under **Test users**. Testing grants for Gmail scopes can expire after seven
   days, requiring reconnection; this is expected in local testing.
3. APIs & Services → Library → Gmail API → Enable.
4. Google Auth Platform → Data Access: add only `gmail.readonly` and `gmail.send`.
   The app asks for those same scopes during connection. Review the requested
   access when authorizing the dedicated mailbox.
5. Clients → Create client → **Web application**, name `ResolveAI Local`.
   Authorized redirect URI must be exactly:

   `http://localhost:8000/integrations/gmail/callback`

   No JavaScript origin is needed for this server OAuth flow. Download the client
   JSON privately after creation; do not attach it to chat or commit it.

## Gemini

Open https://aistudio.google.com/api-keys and create a key for the intended project.
If the project is absent, import/select it in AI Studio. Keep the project on its
free tier for initial synthetic tests; billing activation is a separate decision.
Use a text model available to your account that supports generateContent and
structured output. The setup helper asks for its model ID. Do not confuse your
Gemini website subscription with Gemini API billing.

## Private local configuration

From the repository root run:

```powershell
.\.venv\Scripts\python.exe tools/setup_local.py
```

Enter the path to the downloaded **Web application** JSON, paste the Gemini key
into the hidden prompt and provide the model ID. The helper creates encryption
material automatically and writes config/database under `%LOCALAPPDATA%\ResolveAI`,
outside the repo and OneDrive. On Windows the directory is restricted to the
current user's SID; keys are not echoed. Existing configuration is not overwritten.

Then run each command in a separate terminal from the repository root:

```powershell
.\.venv\Scripts\python.exe tools/run_local.py api
.\.venv\Scripts\python.exe tools/run_local.py worker
.\.venv\Scripts\python.exe tools/run_local.py frontend
```

Open http://localhost:5173, create a local workspace and use Integrations → Connect
Gmail. Complete sign-in/consent yourself, then return to the workspace. The API
suppresses access logs so short-lived OAuth callback codes are not logged.
Outbound sending stays disabled. A later test send requires explicit authorization
for a specific recipient and message.

The helper intentionally uses SQLite for local tests; production uses PostgreSQL.
No provider connection is verified merely by generating this configuration.

Official references: [Google consent setup](https://developers.google.com/workspace/guides/configure-oauth-consent),
[server OAuth](https://developers.google.com/workspace/gmail/api/auth/web-server),
[Gemini keys](https://ai.google.dev/gemini-api/docs/api-key),
[Gemini billing](https://ai.google.dev/gemini-api/docs/billing/).
