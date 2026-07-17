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
            "channel": "Web Form",
            "reference_id": "ORDER-48291",
        },
    )
    assert created.status_code == 201
    created_payload = created.json()
    ticket_id = created_payload["id"]
    assert created_payload["category"] == "Account Access"
    assert created_payload["confidence"] >= 80
    assert created_payload["reference_id"] == "ORDER-48291"
    assert len(created_payload["agent_steps"]) == 5

    ticket_list = client.get("/tickets").json()["items"]
    assert ticket_list[0]["id"] == ticket_id

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


def test_custom_delayed_order_runs_deterministic_triage() -> None:
    response = client.post(
        "/tickets",
        json={
            "subject": "Delayed order and refund request",
            "message": "My order has been delayed for 6 days and I'm frustrated. I want a refund or a clear update.",
            "customer_name": "Jordan Lee",
            "customer_email": "jordan.lee@example.com",
            "channel": "Web Form",
            "reference_id": "ORDER-48291",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["category"] == "Refund Request"
    assert payload["priority"] == "High"
    assert payload["sentiment"] == "Frustrated"
    assert payload["escalation_needed"] is True
    assert "order is delayed" in payload["final_response"]

