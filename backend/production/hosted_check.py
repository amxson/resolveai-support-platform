"""Exercise a deployed workspace using isolated, temporary tenant records.

Load the server DATABASE_URL privately before running. No real mailbox is added,
no message is sent, and the AI worker check uses no knowledge/provider call.
"""

import os
import secrets
import time
from uuid import uuid4

import httpx
from argon2 import PasswordHasher
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from production.database import Base, Membership, Organization, User

BASE = "https://resolveai-support-platform.vercel.app/api"


def main():
    engine = create_engine(os.environ["DATABASE_URL"], hide_parameters=True)
    org_ids, user_ids = [], []
    clients = []
    checks = []

    def passed(name):
        checks.append(name)
        print("PASS:", name, flush=True)

    try:
        for _ in range(2):
            org_id, user_id = str(uuid4()), str(uuid4())
            email, password = (
                f"acceptance-{user_id}@example.com",
                secrets.token_urlsafe(32),
            )
            with Session(engine) as db, db.begin():
                db.add(Organization(id=org_id, name="Temporary hosted acceptance"))
                db.add(
                    User(
                        id=user_id,
                        email=email,
                        password_hash=PasswordHasher().hash(password),
                    )
                )
                db.flush()
                db.add(
                    Membership(organization_id=org_id, user_id=user_id, role="owner")
                )
            org_ids.append(org_id)
            user_ids.append(user_id)
            client = httpx.Client(base_url=BASE, timeout=90, follow_redirects=False)
            clients.append(client)
            login = client.post(
                "/auth/login", json={"email": email, "password": password}
            )
            assert login.status_code == 200, f"login HTTP {login.status_code}"
            cookie = login.headers["set-cookie"].lower()
            assert (
                "secure" in cookie and "httponly" in cookie and "samesite=lax" in cookie
            )
            client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        owner, other = clients
        passed("HTTPS login through Vercel proxy and secure session cookies")
        assert (
            owner.get("/auth/session").json()["csrf_token"]
            == owner.headers["X-CSRF-Token"]
        )
        assert (
            owner.post(
                "/auth/signup",
                json={
                    "email": "closed@example.com",
                    "password": "acceptance-password-42",
                    "organization": "Closed registration",
                },
            ).status_code
            == 403
        )
        passed("Session restoration and closed public registration")
        created = owner.post(
            "/tickets",
            json={
                "subject": "Synthetic hosted acceptance",
                "customer_email": "customer@example.com",
                "message": "Synthetic acceptance message with no policy match.",
            },
        )
        assert created.status_code == 201
        tid = created.json()["id"]
        assert other.get(f"/tickets/{tid}").status_code == 404
        assert other.get("/tickets").json() == []
        csrf = owner.headers.pop("X-CSRF-Token")
        assert (
            owner.post(
                f"/tickets/{tid}/notes", json={"body": "Should be denied"}
            ).status_code
            == 403
        )
        owner.headers["X-CSRF-Token"] = csrf
        assert (
            owner.post(
                f"/tickets/{tid}/notes", json={"body": "Hosted acceptance note"}
            ).status_code
            == 201
        )
        passed("Ticket persistence, tenant isolation, notes and CSRF enforcement")
        uploaded = owner.post(
            f"/tickets/{tid}/attachments",
            content=b"Private synthetic receipt",
            headers={
                "X-Filename": "receipt.txt",
                "Content-Type": "application/octet-stream",
            },
        )
        assert uploaded.status_code == 201
        fid = uploaded.json()["id"]
        assert owner.get(f"/files/{fid}").content == b"Private synthetic receipt"
        assert other.get(f"/files/{fid}").status_code == 404
        passed("Authenticated file upload/download and cross-tenant denial")
        assert owner.post(f"/tickets/{tid}/analyze").status_code == 202
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            job = owner.get(f"/tickets/{tid}/analysis").json()[0]
            if job["status"] in {"completed", "failed", "conflict"}:
                break
            time.sleep(2)
        assert job["status"] == "completed", (
            "Embedded worker did not complete the no-policy job"
        )
        assert (
            job["result"]["provider_called"] is False
            and job["result"]["escalate"] is True
        )
        passed("Embedded worker execution and escalation without invented policy")
        version = owner.get(f"/tickets/{tid}").json()["ticket"]["draft_version"]
        saved = owner.put(
            f"/tickets/{tid}/draft",
            json={"body": "Synthetic reviewed reply", "version": version},
        )
        assert saved.status_code == 200
        version = saved.json()["version"]
        assert (
            owner.post(f"/tickets/{tid}/approve", json={"version": version}).status_code
            == 200
        )
        assert (
            owner.post(
                f"/tickets/{tid}/send",
                json={"version": version, "recipient": "customer@example.com"},
            ).status_code
            == 403
        )
        assert (
            owner.put(
                f"/tickets/{tid}/draft",
                json={"body": "Edited synthetic reply", "version": version},
            ).status_code
            == 200
        )
        assert owner.get(f"/tickets/{tid}").json()["ticket"]["approved_version"] is None
        passed("Versioned approval, edit invalidation and outbound sending disabled")
        document = owner.post(
            "/knowledge/documents",
            content=b"Synthetic acceptance policy. This is isolated test content.",
            headers={
                "X-Filename": "acceptance-policy.txt",
                "Content-Type": "application/octet-stream",
            },
        )
        assert document.status_code == 201
        assert len(owner.get("/knowledge").json()) == 1
        assert other.get("/knowledge").json() == []
        passed("Knowledge document ingestion and tenant isolation")
        assert owner.post("/auth/logout").status_code == 204
        assert owner.get("/tickets").status_code == 401
        passed("Logout revokes hosted session")
    finally:
        for client in clients:
            client.close()
        with engine.begin() as db:
            for table in reversed(Base.metadata.sorted_tables):
                if "organization_id" in table.c:
                    db.execute(
                        delete(table).where(table.c.organization_id.in_(org_ids))
                    )
            db.execute(delete(Organization).where(Organization.id.in_(org_ids)))
            db.execute(delete(User).where(User.id.in_(user_ids)))
        engine.dispose()
        print("Temporary acceptance records removed; existing workspaces preserved.")
    print(f"Hosted checks passed: {len(checks)}")


if __name__ == "__main__":
    main()
