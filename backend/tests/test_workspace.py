"""Exercise API security boundaries using a real migrated database."""

import os

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select

from production.app import create_app
from production.database import Session, now

PASSWORD = "a-long-test-password-42"


@pytest.fixture
def application(tmp_path, monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{tmp_path / 'workspace.db'}")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("APP_ENV", "test")
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    app = create_app(url, secure_cookies=False)
    yield app
    app.state.engine.dispose()
    if os.environ.get("TEST_DATABASE_URL"):
        command.downgrade(config, "base")


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
    url = str(application.state.engine.url)
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
