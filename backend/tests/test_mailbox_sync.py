import base64

from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import select
from test_workspace import account

from production import gmail
from production.database import Mailbox, Membership, Message, StoredFile, Ticket


def test_scheduled_pages_resume_and_import_encrypted_attachments(
    application, monkeypatch
):
    client = account(application)
    key = Fernet.generate_key()
    monkeypatch.setenv("FILE_ENCRYPTION_KEY", key.decode())
    monkeypatch.setattr(gmail, "access_token", lambda mailbox: "test-token")
    with application.state.sessions.begin() as db:
        member = db.scalar(select(Membership))
        org_id = member.organization_id
        db.add(
            Mailbox(
                organization_id=org_id,
                email="support@example.com",
                refresh_token="encrypted",
                sync_actor_id=member.user_id,
            )
        )

    pages = []

    def provider(token, method, path, **kwargs):
        if path == "messages":
            params = kwargs["params"]
            pages.append(dict(params))
            if params.get("pageToken") == "page-two":
                return {"messages": [{"id": "m2"}]}
            return {"messages": [{"id": "m1"}], "nextPageToken": "page-two"}
        return {
            "threadId": "thread-one",
            "payload": {
                "headers": [
                    {"name": "From", "value": "customer@example.com"},
                    {"name": "Subject", "value": "Shipping inquiry"},
                ],
                "parts": [
                    {
                        "mimeType": "text/plain",
                        "body": {
                            "data": base64.urlsafe_b64encode(
                                b"Where is the parcel?"
                            ).decode()
                        },
                    },
                    {
                        "filename": "receipt.txt",
                        "body": {
                            "data": base64.urlsafe_b64encode(
                                b"private receipt"
                            ).decode(),
                            "size": 15,
                        },
                    },
                ],
            },
        }

    monkeypatch.setattr(gmail, "gmail", provider)
    assert gmail.sync_due(application.state.sessions)
    with application.state.sessions.begin() as db:
        mailbox = db.get(Mailbox, org_id)
        assert mailbox.sync_cursor == "page-two" and mailbox.synced_after == 0
        mailbox.next_sync_at = 0
    # A new worker invocation reads the saved cursor, not process-local state.
    assert gmail.sync_due(application.state.sessions)
    assert pages[1]["pageToken"] == "page-two"
    with application.state.sessions() as db:
        mailbox = db.get(Mailbox, org_id)
        assert mailbox.sync_cursor is None and mailbox.synced_after > 0
        assert len(list(db.scalars(select(Ticket)))) == 1
        assert len(list(db.scalars(select(Message)))) == 2
        files = list(db.scalars(select(StoredFile)))
        assert len(files) == 2
        assert all("private receipt" not in f.encrypted_data for f in files)
        assert (
            Fernet(key).decrypt(files[0].encrypted_data.encode()) == b"private receipt"
        )
    assert client.get("/tickets").status_code == 200


def test_scheduled_revoked_grant_requires_reconnection(application, monkeypatch):
    account(application)
    with application.state.sessions.begin() as db:
        member = db.scalar(select(Membership))
        org_id = member.organization_id
        db.add(
            Mailbox(
                organization_id=org_id,
                email="support@example.com",
                refresh_token="encrypted",
                sync_actor_id=member.user_id,
            )
        )

    def revoked(mailbox):
        raise HTTPException(409, "private provider message")

    monkeypatch.setattr(gmail, "access_token", revoked)
    assert not gmail.sync_due(application.state.sessions)
    with application.state.sessions() as db:
        mailbox = db.get(Mailbox, org_id)
        assert mailbox.status == "reconnect_required"
        assert mailbox.sync_failures == 1 and mailbox.next_sync_at > 0
        assert mailbox.sync_error == "HTTPException"
    assert not gmail.sync_due(application.state.sessions)
