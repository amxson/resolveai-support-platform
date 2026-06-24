"""Deterministic ticket hints for the support workflow."""

from __future__ import annotations


RULES = (
    (
        ("refund", "return", "money back", "changed my mind"),
        "Refund request",
        "Refunds",
    ),
    (
        ("damaged", "cracked", "broken", "defective"),
        "Damaged product",
        "Damaged Products",
    ),
    (
        ("charged", "card", "payment", "billing", "duplicate charge"),
        "Payment issue",
        "Payment Issues",
    ),
    (
        ("log in", "login", "password", "reset email", "account"),
        "Account access issue",
        "Account Access",
    ),
    (
        ("delivery", "tracking", "arrive", "package", "order was supposed"),
        "Delivery issue",
        "Delivery Delays",
    ),
)

DEFAULT_CATEGORY = "General question"
DEFAULT_POLICY = "General Questions"


def suggest_ticket_rules(message: str) -> dict[str, str]:
    """Return deterministic category and policy hints based on obvious keywords."""
    normalized_message = message.lower()

    for keywords, category, policy in RULES:
        if any(keyword in normalized_message for keyword in keywords):
            return {
                "suggested_category": category,
                "suggested_policy": policy,
            }

    return {
        "suggested_category": DEFAULT_CATEGORY,
        "suggested_policy": DEFAULT_POLICY,
    }
