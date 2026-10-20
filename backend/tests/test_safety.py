import importlib
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from app.models import TicketCreate
from app.services.store import TicketStore, StoreFullError

main = importlib.import_module("app.main")
client = TestClient(main.app)
PAYLOAD = {
    "subject": "Account recovery",
    "message": "Password reset is not working.",
    "customer_name": "Demo User",
    "customer_email": "demo@example.com",
}


@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    monkeypatch.setattr(
        main, "store", TicketStore(main.workflow.build_demo_tickets(main.DEMO_TICKETS))
    )
    main.write_times.clear()
    yield
    main.write_times.clear()


def test_whitespace_only_input_is_rejected():
    assert (
        client.post("/tickets", json={**PAYLOAD, "customer_name": "   "}).status_code
        == 422
    )


def test_ai_mode_requires_operator_auth_before_provider(monkeypatch):
    monkeypatch.setattr(main.settings, "demo_mode", False)
    monkeypatch.setattr(main.settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(main.settings, "api_token", "operator-test")
    with patch.object(main.workflow, "analyze") as provider:
        assert client.post("/tickets", json=PAYLOAD).status_code == 401
        assert client.post("/tickets/TICK-1001/analyze").status_code == 401
        assert client.post("/tickets/TICK-1001/generate-response").status_code == 401
        provider.assert_not_called()
    with patch.object(main.workflow, "analyze", side_effect=lambda ticket: ticket):
        assert (
            client.post(
                "/tickets",
                json=PAYLOAD,
                headers={"Authorization": "Bearer operator-test"},
            ).status_code
            == 201
        )


def test_ai_mode_without_operator_token_fails_closed(monkeypatch):
    monkeypatch.setattr(main.settings, "demo_mode", False)
    monkeypatch.setattr(main.settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(main.settings, "api_token", "")
    assert (
        client.post(
            "/tickets", json=PAYLOAD, headers={"Authorization": "Bearer "}
        ).status_code
        == 401
    )


def test_provider_details_never_reach_response():
    with patch.object(
        main.workflow, "analyze", side_effect=RuntimeError("SECRET_PROVIDER_DETAIL")
    ):
        response = client.post("/tickets", json=PAYLOAD)
    assert response.status_code == 502
    assert "SECRET_PROVIDER_DETAIL" not in response.text


def test_write_limit_returns_retry_after(monkeypatch):
    monkeypatch.setattr(main.settings, "writes_per_minute", 1)
    assert client.post("/tickets", json=PAYLOAD).status_code == 201
    response = client.post("/tickets", json=PAYLOAD)
    assert response.status_code == 429 and response.headers["retry-after"] == "60"


def test_store_capacity_checked_before_analysis(monkeypatch):
    monkeypatch.setattr(
        main,
        "store",
        TicketStore(main.workflow.build_demo_tickets(main.DEMO_TICKETS), max_tickets=6),
    )
    with patch.object(main.workflow, "analyze") as provider:
        assert client.post("/tickets", json=PAYLOAD).status_code == 503
        provider.assert_not_called()


def test_concurrent_ids_and_bounded_storage():
    store = TicketStore([], max_tickets=2)
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(lambda _: store.next_id(), range(100)))
    assert len(set(ids)) == 100
    template = main.store.list()[0]
    for ticket_id in ids[:2]:
        store.save(template.model_copy(update={"id": ticket_id}))
    with pytest.raises(StoreFullError):
        store.save(template.model_copy(update={"id": ids[2]}))
    detached = store.get(ids[0])
    detached.subject = "changed"
    assert store.get(ids[0]).subject != "changed"


def test_empty_store_analytics_does_not_divide_by_zero(monkeypatch):
    monkeypatch.setattr(main, "store", TicketStore([]))
    assert client.get("/analytics").json()["resolution_rate"] == 0
