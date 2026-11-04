import json
from types import SimpleNamespace

import httpx
import pytest

from production.ai import analyze


def test_missing_knowledge_escalates_without_a_provider_call(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-key")
    monkeypatch.setenv("GEMINI_MODEL", "test-model")
    result = analyze("missing order", [], [])
    assert result["escalate"] and not result["provider_called"]
    assert result["draft"] == ""


@pytest.mark.parametrize("valid", [True, False])
def test_provider_schema_and_citation_validation(monkeypatch, valid):
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-key")
    monkeypatch.setenv("GEMINI_MODEL", "test-model")
    output = {
        "category": "shipping",
        "priority": "medium",
        "sentiment": "neutral",
        "draft": "We will review your order.",
        "citations": [
            {
                "article_id": "policy" if valid else "other-tenant",
                "quote": "Orders arrive within five days.",
            }
        ],
        "escalate": False,
        "explanation": "Relevant policy found",
    }

    def provider(request):
        payload = json.loads(request.content)
        assert "untrusted" in payload["systemInstruction"]["parts"][0]["text"]
        assert payload["generationConfig"]["responseJsonSchema"]
        assert "tools" not in payload
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": json.dumps(output)}]}}],
                "usageMetadata": {"totalTokenCount": 123},
            },
        )

    arguments = (
        "order delivery",
        [SimpleNamespace(kind="incoming", body="Where is my order?")],
        [
            SimpleNamespace(
                id="policy",
                title="Shipping",
                content="Order delivery policy. Orders arrive within five days.",
                version=1,
            )
        ],
    )
    if valid:
        result = analyze(*arguments, transport=httpx.MockTransport(provider))
        assert result["usage"]["totalTokenCount"] == 123
        assert result["cost_usd"] is None
    else:
        with pytest.raises(ValueError, match="invalid_citations"):
            analyze(*arguments, transport=httpx.MockTransport(provider))
