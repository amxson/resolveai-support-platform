"""Gmail channel. No credentials are read from connected Codex accounts."""

import base64
import os
import secrets
from email.message import EmailMessage
from email.utils import parseaddr
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, MultiFernet
from fastapi import Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select

from production.database import (
    Audit,
    Mailbox,
    MailReceipt,
    MailThread,
    Membership,
    Message,
    OAuthState,
    Outbound,
    Ticket,
    now,
)
from production.files import MAX_SIZE, clean_file, store_file

SCOPES = "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.send"


def cipher():
    return MultiFernet(
        [
            Fernet(key.strip().encode())
            for key in os.environ["OAUTH_ENCRYPTION_KEY"].split(",")
        ]
    )


def oauth_config():
    values = {
        key: os.environ.get(key, "")
        for key in [
            "GOOGLE_CLIENT_ID",
            "GOOGLE_CLIENT_SECRET",
            "GOOGLE_REDIRECT_URI",
            "OAUTH_ENCRYPTION_KEY",
        ]
    }
    if not all(values.values()):
        raise HTTPException(503, "Gmail OAuth is not configured")
    cipher()
    return values


def token_request(data):
    config = oauth_config()
    with httpx.Client(timeout=20, follow_redirects=False) as client:
        response = client.post(
            "https://oauth2.googleapis.com/token",
            data={
                **data,
                "client_id": config["GOOGLE_CLIENT_ID"],
                "client_secret": config["GOOGLE_CLIENT_SECRET"],
            },
        )
        if response.status_code != 200:
            if (
                response.status_code == 400
                and response.json().get("error") == "invalid_grant"
            ):
                raise HTTPException(
                    409, "Gmail grant expired or revoked; reconnect mailbox"
                )
            raise HTTPException(502, "Google authorization failed; reconnect mailbox")
        return response.json()


def gmail(token, method, path, **kwargs):
    with httpx.Client(timeout=30, follow_redirects=False) as client:
        response = client.request(
            method,
            "https://gmail.googleapis.com/gmail/v1/users/me/" + path,
            headers={"Authorization": "Bearer " + token},
            **kwargs,
        )
        if response.status_code >= 400:
            raise HTTPException(502, "Gmail operation failed; check connection")
        return response.json()


def access_token(mailbox):
    return token_request(
        {
            "grant_type": "refresh_token",
            "refresh_token": cipher().decrypt(mailbox.refresh_token.encode()).decode(),
        }
    )["access_token"]


def plain_text(part):
    if part.get("mimeType") == "text/plain":
        data = part.get("body", {}).get("data", "")
        if len(data) > 30000:
            return "[Message exceeds ingestion limit; inspect original mailbox]"
        return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode(
            "utf-8", errors="replace"
        )
    return "\n".join(plain_text(p) for p in part.get("parts", []))[:20000]


def file_parts(part, depth=0):
    if depth > 10:
        return
    if part.get("filename"):
        yield part
    for child in part.get("parts", []):
        yield from file_parts(child, depth + 1)


class SendInput(BaseModel):
    version: int
    recipient: EmailStr


def register(app, principal, db_session, find, admin, audit, digest, sessions):
    @app.get("/integrations/gmail")
    def status(member=Depends(principal), db=Depends(db_session, scope="function")):
        admin(member)
        mailbox = db.get(Mailbox, member.organization_id)
        return {
            "email": mailbox.email if mailbox else None,
            "status": mailbox.status if mailbox else "disconnected",
        }

    @app.post("/integrations/gmail/connect")
    def connect(member=Depends(principal), db=Depends(db_session, scope="function")):
        admin(member)
        config = oauth_config()
        state = secrets.token_urlsafe(32)
        db.add(
            OAuthState(
                token_hash=digest(state),
                organization_id=member.organization_id,
                user_id=member.user_id,
                expires_at=now() + 600,
            )
        )
        return {
            "url": "https://accounts.google.com/o/oauth2/v2/auth?"
            + urlencode(
                {
                    "client_id": config["GOOGLE_CLIENT_ID"],
                    "redirect_uri": config["GOOGLE_REDIRECT_URI"],
                    "response_type": "code",
                    "scope": SCOPES,
                    "access_type": "offline",
                    "prompt": "consent",
                    "state": state,
                }
            )
        }

    @app.get("/integrations/gmail/callback")
    def callback(
        code: str,
        state: str,
        member=Depends(principal),
        db=Depends(db_session, scope="function"),
    ):
        admin(member)
        record = db.scalar(
            select(OAuthState)
            .where(OAuthState.token_hash == digest(state))
            .with_for_update()
        )
        if (
            not record
            or record.expires_at < now()
            or record.organization_id != member.organization_id
            or record.user_id != member.user_id
        ):
            raise HTTPException(400, "Invalid OAuth state")
        config = oauth_config()
        tokens = token_request(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": config["GOOGLE_REDIRECT_URI"],
            }
        )
        if not tokens.get("refresh_token") or not all(
            s in tokens.get("scope", "").split() for s in SCOPES.split()
        ):
            raise HTTPException(
                400, "Grant both requested permissions and offline access"
            )
        profile = gmail(tokens["access_token"], "GET", "profile")
        existing = db.get(Mailbox, member.organization_id)
        if existing and existing.email != profile["emailAddress"]:
            raise HTTPException(
                409, "Disconnect the existing mailbox before changing accounts"
            )
        db.merge(
            Mailbox(
                organization_id=member.organization_id,
                email=profile["emailAddress"],
                refresh_token=cipher()
                .encrypt(tokens["refresh_token"].encode())
                .decode(),
                status="connected",
                sync_actor_id=member.user_id,
            )
        )
        db.delete(record)
        audit(db, member, "gmail.connected", member.organization_id)
        return {
            "connected": True,
            "message": "Return to the workspace and refresh integrations",
        }

    @app.delete("/integrations/gmail", status_code=204)
    def disconnect(member=Depends(principal), db=Depends(db_session, scope="function")):
        admin(member)
        mailbox = db.get(Mailbox, member.organization_id)
        if mailbox:
            mailbox.status = "disconnected"
            mailbox.refresh_token = ""
            audit(db, member, "gmail.disconnected", member.organization_id)

    @app.post("/integrations/gmail/sync")
    def sync(member=Depends(principal), db=Depends(db_session, scope="function")):
        return sync_mailbox(db, member, audit)

    @app.post("/tickets/{ticket_id}/send")
    def send(
        ticket_id: str,
        payload: SendInput,
        member=Depends(principal),
        db=Depends(db_session, scope="function"),
    ):
        # This gate defaults closed even with a connected mailbox.
        if os.environ.get("ENABLE_EMAIL_SEND") != "true":
            raise HTTPException(403, "Outbound email is disabled by the operator")
        ticket = find(db, Ticket, ticket_id, member, True)
        if (
            ticket.approved_version != payload.version
            or ticket.draft_version != payload.version
            or not ticket.draft
        ):
            raise HTTPException(409, "Approve this exact draft version before sending")
        if payload.recipient != ticket.customer_email:
            raise HTTPException(422, "Confirm the conversation recipient")
        existing = db.scalar(
            select(Outbound).where(
                Outbound.organization_id == member.organization_id,
                Outbound.ticket_id == ticket_id,
                Outbound.draft_version == payload.version,
            )
        )
        if existing:
            return {"status": existing.status, "provider_id": existing.provider_id}
        mailbox = db.get(Mailbox, member.organization_id)
        thread = db.scalar(
            select(MailThread).where(
                MailThread.organization_id == member.organization_id,
                MailThread.ticket_id == ticket_id,
            )
        )
        if not mailbox or mailbox.status != "connected" or not thread:
            raise HTTPException(409, "Only imported Gmail conversations can be sent")
        token = access_token(mailbox)
        # Persist the attempt in an independent transaction before external I/O.
        # Ambiguous failures are never automatically retried, including process crashes.
        with sessions.begin() as outbox:
            attempt = Outbound(
                organization_id=member.organization_id,
                ticket_id=ticket_id,
                draft_version=payload.version,
            )
            outbox.add(attempt)
            outbox.flush()
            attempt_id = attempt.id
        email = EmailMessage()
        email["To"], email["From"] = ticket.customer_email, mailbox.email
        email["Subject"] = (
            ticket.subject
            if ticket.subject.lower().startswith("re:")
            else "Re: " + ticket.subject
        )
        if (
            thread.reply_message_id
            and "\n" not in thread.reply_message_id
            and "\r" not in thread.reply_message_id
        ):
            email["In-Reply-To"] = thread.reply_message_id
            email["References"] = thread.reply_message_id
        email["Message-ID"] = f"<resolveai-{attempt_id}@{mailbox.email.split('@')[-1]}>"
        email.set_content(ticket.draft)
        try:
            result = gmail(
                token,
                "POST",
                "messages/send",
                json={
                    "threadId": thread.thread_id,
                    "raw": base64.urlsafe_b64encode(email.as_bytes()).decode(),
                },
            )
        except Exception:
            with sessions.begin() as outbox:
                outbox.get(Outbound, attempt_id).status = "unknown"
            raise HTTPException(
                502, "Send outcome uncertain; inspect Gmail before any further action"
            ) from None
        with sessions.begin() as outbox:
            attempt = outbox.get(Outbound, attempt_id)
            attempt.status, attempt.provider_id = "accepted", result["id"]
        audit(
            db,
            member,
            "gmail.send_accepted",
            ticket_id,
            provider_id=result["id"],
            version=payload.version,
        )
        return {
            "status": "accepted",
            "provider_id": result["id"],
            "delivery_verified": False,
        }


def sync_mailbox(db, member, audit):
    if member.role not in {"owner", "admin"}:
        raise HTTPException(403, "Administrator permission required")
    # Serialize mailbox ingestion so duplicate imports cannot create duplicate tickets.
    mailbox = db.scalar(
        select(Mailbox)
        .where(Mailbox.organization_id == member.organization_id)
        .with_for_update()
    )
    if not mailbox or mailbox.status != "connected":
        raise HTTPException(409, "Connect Gmail first")
    token = access_token(mailbox)
    if not mailbox.sync_cursor:
        mailbox.scan_started = now()
    params = {"labelIds": "INBOX", "maxResults": 10}
    if mailbox.sync_cursor:
        params["pageToken"] = mailbox.sync_cursor
    if mailbox.synced_after:
        params["q"] = f"after:{max(0, int(mailbox.synced_after) - 600)}"
    listing = gmail(token, "GET", "messages", params=params)
    imported = 0
    for item in listing.get("messages", []):
        if db.get(MailReceipt, (member.organization_id, item["id"])):
            continue
        message = gmail(
            token, "GET", "messages/" + item["id"], params={"format": "full"}
        )
        headers = {
            h["name"].lower(): h["value"] for h in message["payload"].get("headers", [])
        }
        sender = parseaddr(headers.get("from", ""))[1]
        try:
            sender = str(SendInput(version=0, recipient=sender).recipient)
        except ValueError:
            continue
        thread = db.get(MailThread, (member.organization_id, message["threadId"]))
        if not thread:
            ticket = Ticket(
                organization_id=member.organization_id,
                subject=headers.get("subject", "(No subject)")[:200],
                customer_email=sender,
            )
            db.add(ticket)
            db.flush()
            thread = MailThread(
                organization_id=member.organization_id,
                thread_id=message["threadId"],
                ticket_id=ticket.id,
                reply_message_id=headers.get("message-id", "")[:1000],
            )
            db.add(thread)
        else:
            ticket = db.scalar(
                select(Ticket)
                .where(
                    Ticket.id == thread.ticket_id,
                    Ticket.organization_id == member.organization_id,
                )
                .with_for_update(key_share=True)
            )
            ticket.draft_version += 1
            ticket.approved_version = None
            ticket.status = "open"
        body = (
            plain_text(message["payload"])
            or "[No plain-text part; inspect original mailbox]"
        )
        db.add(
            Message(
                organization_id=member.organization_id,
                ticket_id=thread.ticket_id,
                kind="incoming",
                body=body,
            )
        )
        db.add(
            MailReceipt(organization_id=member.organization_id, provider_id=item["id"])
        )
        for index, part in enumerate(file_parts(message["payload"])):
            try:
                info = part.get("body", {})
                if index >= 10 or info.get("size", 0) > MAX_SIZE:
                    raise HTTPException(422, "Attachment exceeds import limits")
                encoded = info.get("data", "")
                if info.get("attachmentId"):
                    encoded = gmail(
                        token,
                        "GET",
                        "messages/"
                        + item["id"]
                        + "/attachments/"
                        + info["attachmentId"],
                    ).get("data", "")
                if len(encoded) > (MAX_SIZE * 4 // 3 + 8):
                    raise HTTPException(422, "Attachment exceeds size limit")
                data = base64.b64decode(
                    encoded + "=" * (-len(encoded) % 4),
                    altchars=b"-_",
                    validate=True,
                )
                filename, content_type = clean_file(part["filename"], data)
                store_file(
                    db,
                    member,
                    filename,
                    content_type,
                    data,
                    ticket_id=thread.ticket_id,
                )
            except (ValueError, HTTPException) as error:
                # Keep an explicit record of a rejected attachment; never execute it.
                if isinstance(error, HTTPException) and error.status_code == 503:
                    raise
                db.add(
                    Message(
                        organization_id=member.organization_id,
                        ticket_id=thread.ticket_id,
                        kind="internal",
                        body="An incoming attachment could not be imported within allowed file types/size limits. Inspect the original mailbox.",
                    )
                )
        imported += 1
    mailbox.sync_cursor = listing.get("nextPageToken")
    if not mailbox.sync_cursor:
        mailbox.synced_after = mailbox.scan_started
    mailbox.next_sync_at = now() + (2 if mailbox.sync_cursor else 60)
    mailbox.sync_failures = 0
    mailbox.sync_error = None
    audit(db, member, "gmail.synced", member.organization_id, imported=imported)
    return {
        "imported": imported,
        "more_pages": bool(mailbox.sync_cursor),
    }


def sync_due(sessions):
    org_id = None
    try:
        with sessions.begin() as db:
            mailbox = db.scalar(
                select(Mailbox)
                .where(Mailbox.status == "connected", Mailbox.next_sync_at <= now())
                .order_by(Mailbox.next_sync_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if not mailbox:
                return False
            org_id = mailbox.organization_id
            member = (
                db.get(Membership, (org_id, mailbox.sync_actor_id))
                if mailbox.sync_actor_id
                else None
            )
            if not member or member.role not in {"owner", "admin"}:
                member = db.scalar(
                    select(Membership).where(
                        Membership.organization_id == org_id, Membership.role == "owner"
                    )
                )
            if not member:
                mailbox.status = "disconnected"
                mailbox.refresh_token = ""
                return True

            def record(db, actor, action, resource, **details):
                db.add(
                    Audit(
                        organization_id=actor.organization_id,
                        actor_id=actor.user_id,
                        action=action,
                        resource_id=resource,
                        details=details,
                    )
                )

            sync_mailbox(db, member, record)
        return True
    except Exception as error:
        if org_id:
            with sessions.begin() as db:
                mailbox = db.get(Mailbox, org_id)
                if mailbox:
                    mailbox.sync_failures += 1
                    mailbox.sync_error = type(error).__name__
                    mailbox.next_sync_at = now() + min(
                        900, 30 * 2 ** min(mailbox.sync_failures, 5)
                    )
                    if isinstance(error, HTTPException) and error.status_code == 409:
                        mailbox.status = "reconnect_required"
        return False
