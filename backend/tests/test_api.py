"""High-value endpoint tests for demo mode."""

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_reports_demo_mode() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["mode"] == "Demo"


def test_ticket_list_contains_fictional_seed_data() -> None:
    response = client.get("/tickets")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 6
    assert all("Demo data" in ticket["tags"] for ticket in payload["items"])


def test_create_and_analyze_ticket() -> None:
    created = client.post(
        "/tickets",
        json={
            "subject": "Cannot access account",
            "message": "I am locked out and the password reset email never arrives.",
            "customer_name": "Demo User",
            "customer_email": "demo.user@example.com",
        },
    )
    assert created.status_code == 201
    ticket_id = created.json()["id"]

    analyzed = client.post(f"/tickets/{ticket_id}/analyze")
    assert analyzed.status_code == 200
    payload = analyzed.json()
    assert payload["category"] == "Account Access"
    assert payload["confidence"] >= 80
    assert len(payload["agent_steps"]) == 5


def test_filters_and_analytics() -> None:
    assert client.get("/tickets", params={"status": "Escalated"}).json()["total"] >= 1
    analytics = client.get("/analytics")
    assert analytics.status_code == 200
    assert analytics.json()["total_tickets"] >= 6

