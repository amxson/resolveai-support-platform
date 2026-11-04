"""Exercise API security boundaries using a real migrated database."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from production.app import create_app
from production.database import AnalysisJob, Session, now
from production.worker import run_once

PASSWORD = "a-long-test-password-42"


def account(app, email="owner@example.com"):
    client = TestClient(app)
    response = client.post(
        "/auth/signup",
        json={"email": email, "password": PASSWORD, "organization": email},
    )
    assert response.status_code == 201, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return client


def ticket(client):
    response = client.post(
        "/tickets",
        json={
            "subject": "Missing order",
            "customer_email": "customer@example.com",
            "message": "Please check my shipment",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_persistence_approval_and_conflicting_edits(application):
    client = account(application)
    tid = ticket(client)
    assert client.get("/analytics").json()["total_tickets"] == 1
    assert (
        client.put(
            f"/tickets/{tid}/draft", json={"body": "We are checking.", "version": 0}
        ).status_code
        == 200
    )
    assert (
        client.post(f"/tickets/{tid}/approve", json={"version": 1}).json()["sent"]
        is False
    )
    assert (
        client.put(
            f"/tickets/{tid}/draft", json={"body": "Updated response", "version": 1}
        ).status_code
        == 200
    )
    assert (
        client.post(f"/tickets/{tid}/approve", json={"version": 1}).status_code == 409
    )
    assert (
        client.put(
            f"/tickets/{tid}/draft", json={"body": "Stale tab", "version": 1}
        ).status_code
        == 409
    )
    detail = client.get(f"/tickets/{tid}").json()
    assert detail["ticket"]["approved_version"] is None
    url = application.state.engine.url.render_as_string(hide_password=False)
    restarted = TestClient(create_app(url, secure_cookies=False))
    restarted.cookies.update(client.cookies)
    assert (
        restarted.get(f"/tickets/{tid}").json()["ticket"]["draft"] == "Updated response"
    )
    assert {e["action"] for e in client.get("/audit").json()} >= {
        "draft.approved",
        "draft.saved",
        "ticket.created",
    }


def test_all_tenant_boundaries(application):
    owner, other = account(application), account(application, "other@example.com")
    tid = ticket(owner)
    article = owner.post(
        "/knowledge", json={"title": "Private policy", "content": "Only tenant one"}
    ).json()["id"]
    for method, path, data in [
        ("GET", f"/tickets/{tid}", None),
        ("PATCH", f"/tickets/{tid}", {"status": "resolved"}),
        ("POST", f"/tickets/{tid}/notes", {"body": "Attack"}),
        ("PUT", f"/tickets/{tid}/draft", {"body": "Attack", "version": 0}),
        ("POST", f"/tickets/{tid}/approve", {"version": 1}),
        ("POST", f"/tickets/{tid}/reject", {}),
        ("PUT", f"/knowledge/{article}", {"title": "Attack", "content": "Attack"}),
        ("DELETE", f"/knowledge/{article}", None),
    ]:
        assert other.request(method, path, json=data).status_code == 404
    assert other.get("/tickets").json() == []
    assert other.get("/knowledge").json() == []
    assert other.get("/analytics").json()["total_tickets"] == 0
    assert all(e["resource_id"] != tid for e in other.get("/audit").json())
    other_id = other.get("/team").json()[0]["id"]
    assert (
        owner.patch(
            f"/tickets/{tid}", json={"status": "open", "assignee_id": other_id}
        ).status_code
        == 422
    )


def test_invite_replay_roles_revocation(application):
    owner = account(application)
    token = owner.post("/invitations", json={"email": "agent@example.com"}).json()[
        "token"
    ]
    agent = TestClient(application)
    payload = {"email": "agent@example.com", "password": PASSWORD, "token": token}
    response = agent.post("/invitations/accept", json=payload)
    assert response.status_code == 200
    agent.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    assert agent.post("/invitations/accept", json=payload).status_code == 400
    assert (
        agent.post(
            "/invitations", json={"email": "evil@example.com", "role": "admin"}
        ).status_code
        == 403
    )
    assert (
        agent.post("/knowledge", json={"title": "Policy", "content": "No"}).status_code
        == 403
    )
    assert (
        agent.post(
            "/tickets",
            json={
                "subject": "Valid agent ticket",
                "customer_email": "c@example.com",
                "message": "Hello",
            },
        ).status_code
        == 201
    )
    target = next(m for m in owner.get("/team").json() if m["role"] == "agent")
    assert owner.delete(f"/team/{target['id']}").status_code == 204
    assert agent.get("/tickets").status_code == 401
    owner_id = owner.get("/team").json()[0]["id"]
    assert owner.delete(f"/team/{owner_id}").status_code == 403


def test_auth_csrf_expiry_and_logout(application):
    anonymous = TestClient(application)
    assert anonymous.get("/tickets").status_code == 401
    assert (
        anonymous.post(
            "/auth/signup",
            headers={"Origin": "https://evil.example"},
            json={
                "email": "a@example.com",
                "password": PASSWORD,
                "organization": "Attack",
            },
        ).status_code
        == 403
    )
    client = account(application)
    assert (
        client.post(
            "/tickets",
            headers={"X-CSRF-Token": "wrong"},
            json={
                "subject": "Attack",
                "message": "Attack",
                "customer_email": "c@example.com",
            },
        ).status_code
        == 403
    )
    with application.state.sessions.begin() as db:
        session = db.scalar(select(Session))
        assert len(session.token_hash) == 64
        assert session.token_hash != client.cookies["resolveai_session"]
        session.expires_at = now() - 1
    assert client.get("/tickets").status_code == 401
    login = client.post(
        "/auth/login", json={"email": "owner@example.com", "password": PASSWORD}
    )
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    assert client.post("/auth/logout").status_code == 204
    assert client.get("/tickets").status_code == 401


def test_rate_limits_readiness_and_no_demo(application):
    client = TestClient(application)
    assert client.get("/ready").status_code == 200
    for _ in range(10):
        assert (
            client.post(
                "/auth/login",
                json={"email": "missing@example.com", "password": PASSWORD},
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/auth/login", json={"email": "missing@example.com", "password": PASSWORD}
        ).status_code
        == 429
    )
    assert client.get("/health").json()["mode"] == "workspace"
    owner = account(application)
    assert owner.get("/tickets").json() == []
    assert owner.get("/knowledge").json() == []


def test_production_configuration_fails_closed(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(RuntimeError):
        create_app("sqlite://", secure_cookies=False)


def test_existing_session_can_restore_csrf_without_password(application):
    client = account(application)
    original = client.headers.pop("X-CSRF-Token")
    restored = client.get("/auth/session")
    assert restored.status_code == 200
    assert restored.json()["csrf_token"] == original
    assert "resolveai_session" not in restored.text
    assert client.get("/auth/session").json()["csrf_token"] == original
    client.headers["X-CSRF-Token"] = restored.json()["csrf_token"]
    assert ticket(client)
    assert TestClient(application).get("/auth/session").status_code == 401


def test_analysis_jobs_failure_retries_and_human_edit_protection(
    application, monkeypatch
):
    client = account(application)
    other = account(application, "other@example.com")
    tid = ticket(client)
    assert client.post(f"/tickets/{tid}/analyze").status_code == 503
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-key")
    monkeypatch.setenv("GEMINI_MODEL", "test-model")
    job_id = client.post(f"/tickets/{tid}/analyze").json()["job_id"]
    assert client.post(f"/tickets/{tid}/analyze").json()["job_id"] == job_id
    assert other.get(f"/tickets/{tid}/analysis").status_code == 404

    def failing(*args):
        raise TimeoutError("sensitive provider error should not be persisted")

    for _attempt in range(3):
        with application.state.sessions.begin() as db:
            job = db.get(AnalysisJob, job_id)
            job.available_at = 0
        assert run_once(application.state.sessions, failing)
    job = client.get(f"/tickets/{tid}/analysis").json()[0]
    assert job["status"] == "failed" and job["attempts"] == 3
    assert job["error"] == "TimeoutError" and job["result"] == {}
    assert client.get(f"/tickets/{tid}").json()["ticket"]["status"] == "escalated"
    client.post(f"/tickets/{tid}/analyze")
    client.put(f"/tickets/{tid}/draft", json={"body": "Human response", "version": 0})

    def successful(*args):
        return {
            "draft": "Generated response",
            "escalate": False,
            "provider_called": True,
        }

    assert run_once(application.state.sessions, successful)
    assert client.get(f"/tickets/{tid}/analysis").json()[0]["status"] == "conflict"
    assert client.get(f"/tickets/{tid}").json()["ticket"]["draft"] == "Human response"


def test_gmail_oauth_ingestion_duplicates_and_approved_send(application, monkeypatch):
    import base64
    from urllib.parse import parse_qs, urlparse

    from cryptography.fernet import Fernet

    from production import gmail as channel

    client = account(application)
    other = account(application, "other@example.com")
    assert client.post("/integrations/gmail/connect").status_code == 503
    for key in ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI"]:
        monkeypatch.setenv(key, "test-only-value")
    monkeypatch.setenv("OAUTH_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(
        channel,
        "token_request",
        lambda data: {
            "access_token": "test",
            "refresh_token": "private-refresh",
            "scope": channel.SCOPES,
        },
    )
    sent = []

    def provider(token, method, path, **kwargs):
        if path == "profile":
            return {"emailAddress": "support@example.com"}
        if path == "messages":
            return {"messages": [{"id": "m1"}, {"id": "m2"}]}
        if path in {"messages/m1", "messages/m2"}:
            return {
                "threadId": "thread-one",
                "payload": {
                    "mimeType": "text/plain",
                    "headers": [
                        {"name": "From", "value": "Customer <customer@example.com>"},
                        {"name": "Subject", "value": "Where is my order"},
                        {"name": "Message-ID", "value": "<customer-1@example.com>"},
                    ],
                    "body": {
                        "data": base64.urlsafe_b64encode(
                            b"Please check my order"
                        ).decode()
                    },
                },
            }
        if path == "messages/send":
            sent.append(kwargs["json"])
            return {"id": "sent-one"}
        raise AssertionError(path)

    monkeypatch.setattr(channel, "gmail", provider)
    state = parse_qs(
        urlparse(client.post("/integrations/gmail/connect").json()["url"]).query
    )["state"][0]
    assert (
        other.get(
            "/integrations/gmail/callback", params={"state": state, "code": "test"}
        ).status_code
        == 400
    )
    assert (
        client.get(
            "/integrations/gmail/callback", params={"state": state, "code": "test"}
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/integrations/gmail/callback", params={"state": state, "code": "test"}
        ).status_code
        == 400
    )
    assert client.post("/integrations/gmail/sync").json()["imported"] == 2
    assert client.post("/integrations/gmail/sync").json()["imported"] == 0
    tickets = client.get("/tickets").json()
    assert len(tickets) == 1
    tid = tickets[0]["id"]
    assert len(client.get(f"/tickets/{tid}").json()["messages"]) == 2
    assert other.get("/tickets").json() == []
    initial_version = tickets[0]["draft_version"]
    data = {"version": initial_version + 1, "recipient": "customer@example.com"}
    assert client.post(f"/tickets/{tid}/send", json=data).status_code == 403
    monkeypatch.setenv("ENABLE_EMAIL_SEND", "true")
    assert client.post(f"/tickets/{tid}/send", json=data).status_code == 409
    client.put(
        f"/tickets/{tid}/draft",
        json={"body": "We will check your order", "version": initial_version},
    )
    client.post(f"/tickets/{tid}/approve", json={"version": initial_version + 1})
    assert (
        client.post(f"/tickets/{tid}/send", json=data).json()["provider_id"]
        == "sent-one"
    )
    assert client.post(f"/tickets/{tid}/send", json=data).json()["status"] == "accepted"
    assert len(sent) == 1 and sent[0]["threadId"] == "thread-one"
    client.put(
        f"/tickets/{tid}/draft",
        json={"body": "Updated response", "version": initial_version + 1},
    )
    client.post(f"/tickets/{tid}/approve", json={"version": initial_version + 2})

    def timeout(*args, **kwargs):
        raise TimeoutError("Ambiguous outcome")

    monkeypatch.setattr(channel, "gmail", timeout)
    data["version"] = initial_version + 2
    assert client.post(f"/tickets/{tid}/send", json=data).status_code == 502
    assert client.post(f"/tickets/{tid}/send", json=data).json()["status"] == "unknown"

    def newer_message(token, method, path, **kwargs):
        if path == "messages":
            return {"messages": [{"id": "m3"}]}
        return provider(
            token, method, "messages/m2" if path == "messages/m3" else path, **kwargs
        )

    monkeypatch.setattr(channel, "gmail", newer_message)
    assert client.post("/integrations/gmail/sync").json()["imported"] == 1
    current = client.get(f"/tickets/{tid}").json()["ticket"]
    assert current["approved_version"] is None
    assert current["draft_version"] > data["version"]


def test_worker_crash_budget_is_bounded(application, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "test-model")
    client = account(application)
    tid = ticket(client)
    job_id = client.post(f"/tickets/{tid}/analyze").json()["job_id"]
    with application.state.sessions.begin() as db:
        job = db.get(AnalysisJob, job_id)
        job.status, job.attempts, job.lease_until = "running", 3, 0

    def must_not_run(*args):
        pytest.fail("A crashed exhausted job must not call the provider again")

    assert run_once(application.state.sessions, must_not_run)
    assert client.get(f"/tickets/{tid}/analysis").json()[0]["status"] == "failed"
