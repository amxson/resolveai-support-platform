"""Deterministic demo workflow plus optional CrewAI execution adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.config import Settings
from app.data import KNOWLEDGE_ARTICLES
from app.models import (
    AgentStep,
    Customer,
    KnowledgeMatch,
    QualityReview,
    Ticket,
    TicketCreate,
)


CATEGORY_RULES = [
    ("Technical Bug", ("bug", "error", "checkout", "crash", "not working")),
    ("Payment Issue", ("charged", "billing", "payment", "card", "invoice")),
    ("Refund Request", ("refund", "return", "money back", "wrong")),
    ("Account Access", ("login", "log in", "password", "locked out", "reset")),
    ("Damaged Product", ("damaged", "cracked", "broken", "crushed")),
    ("Delivery Issue", ("delivery", "tracking", "shipment", "package", "late")),
    ("Pricing Question", ("pricing", "plan", "tier", "billing", "team")),
]

NEGATIVE_WORDS = ("angry", "frustrated", "disappointed", "unacceptable", "third time")
URGENT_WORDS = ("urgent", "today", "immediately", "locked out", "safety", "event this weekend")


class WorkflowService:
    """Run the portfolio workflow without requiring paid external services."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def mode(self) -> str:
        if not self.settings.demo_mode and self.settings.gemini_api_key:
            return "CrewAI"
        return "Demo"

    def create_ticket(self, ticket_id: str, payload: TicketCreate) -> Ticket:
        now = datetime.now(timezone.utc)
        initials = "".join(part[0] for part in payload.customer_name.split()[:2]).upper()
        return Ticket(
            id=ticket_id,
            subject=payload.subject,
            message=payload.message,
            customer=Customer(
                name=payload.customer_name,
                email=payload.customer_email,
                initials=initials,
            ),
            channel=payload.channel,
            created_at=now,
            updated_at=now,
        )

    def analyze(self, ticket: Ticket, status_override: str | None = None) -> Ticket:
        """Analyze one ticket, falling back safely when AI mode is unavailable."""
        if self.mode == "CrewAI":
            try:
                from app.services.crewai_adapter import run_crewai_workflow

                return run_crewai_workflow(ticket, self.settings)
            except Exception:
                if not self.settings.fallback_on_ai_error:
                    raise

        return self._run_demo_workflow(ticket, status_override=status_override)

    def _run_demo_workflow(self, ticket: Ticket, status_override: str | None = None) -> Ticket:
        message = ticket.message.lower()
        category = self._classify(message)
        sentiment = self._sentiment(message)
        priority = self._priority(message, category, sentiment)
        article = self._match_article(category)
        escalation_needed = priority == "Urgent" or category in {"Technical Bug"} or (
            priority == "High" and category in {"Delivery Issue", "Payment Issue", "Account Access"}
        )
        status = status_override or ("Escalated" if escalation_needed else "In Review")
        confidence = self._confidence(category, message)
        draft = self._draft_reply(ticket, category, escalation_needed)
        final = self._polish_reply(draft, category)
        next_action = self._next_action(category, escalation_needed, status)

        knowledge_match = KnowledgeMatch(
            article_id=article["id"],
            title=article["title"],
            excerpt=article["summary"],
            score=min(98, confidence + 3),
            section=article["category"],
        )
        qa_score = min(99, confidence + 4)
        steps = [
            AgentStep(
                name="Triage Agent",
                role="Classification & urgency",
                summary=f"Classified as {category}; {priority.lower()} priority with {sentiment.lower()} sentiment.",
                confidence=confidence,
                duration_ms=420,
            ),
            AgentStep(
                name="Knowledge Base Agent",
                role="Policy retrieval",
                summary=f"Matched {article['id']} with {min(98, confidence + 3)}% relevance.",
                confidence=min(98, confidence + 3),
                duration_ms=310,
            ),
            AgentStep(
                name="Response Writer Agent",
                role="Reply drafting",
                summary="Drafted a policy-grounded response with a clear next step.",
                confidence=max(80, confidence - 2),
                duration_ms=680,
            ),
            AgentStep(
                name="Quality Review Agent",
                role="Safety & tone review",
                summary="Checked empathy, policy alignment, unsupported promises, and action clarity.",
                confidence=qa_score,
                duration_ms=360,
            ),
            AgentStep(
                name="Decision Agent",
                role="Routing & final action",
                summary=f"Recommended: {next_action}",
                confidence=max(82, confidence - 1),
                duration_ms=240,
            ),
        ]

        return ticket.model_copy(
            update={
                "category": category,
                "priority": priority,
                "sentiment": sentiment,
                "status": status,
                "confidence": confidence,
                "escalation_needed": escalation_needed,
                "suggested_next_action": next_action,
                "reasoning_summary": self._reasoning(category, priority, sentiment, article["id"]),
                "knowledge_match": knowledge_match,
                "draft_response": draft,
                "final_response": final,
                "quality_review": QualityReview(
                    status="Approved with safeguards",
                    score=qa_score,
                    checks=[
                        "Tone and empathy",
                        "Knowledge-base alignment",
                        "No unsupported promise",
                        "Clear next action",
                    ],
                    notes="The prototype review found no policy conflicts and retained a human approval step.",
                ),
                "agent_steps": steps,
                "tags": [category, sentiment, "Demo data"],
                "updated_at": datetime.now(timezone.utc),
            }
        )

    @staticmethod
    def _classify(message: str) -> str:
        scores = [
            (sum(keyword in message for keyword in keywords), category)
            for category, keywords in CATEGORY_RULES
        ]
        best_score, best_category = max(scores, key=lambda item: item[0])
        return best_category if best_score else "General Question"

    @staticmethod
    def _sentiment(message: str) -> str:
        negative_hits = sum(word in message for word in NEGATIVE_WORDS)
        if negative_hits >= 2:
            return "Negative"
        if negative_hits == 1 or any(word in message for word in ("need", "never", "fails", "late")):
            return "Frustrated"
        if any(word in message for word in ("thank", "appreciate", "please")):
            return "Positive"
        return "Neutral"

    @staticmethod
    def _priority(message: str, category: str, sentiment: str) -> str:
        if any(word in message for word in URGENT_WORDS) and category in {
            "Technical Bug",
            "Account Access",
            "Damaged Product",
        }:
            return "Urgent"
        if category == "Technical Bug" or "charged" in message or "six days" in message:
            return "High"
        if sentiment in {"Frustrated", "Negative"} or category in {"Refund Request", "Delivery Issue"}:
            return "Medium"
        return "Low"

    @staticmethod
    def _confidence(category: str, message: str) -> int:
        keyword_hits = next(
            (sum(keyword in message for keyword in words) for name, words in CATEGORY_RULES if name == category),
            1,
        )
        return min(97, 87 + keyword_hits * 2)

    @staticmethod
    def _match_article(category: str) -> dict[str, Any]:
        return next(
            (article for article in KNOWLEDGE_ARTICLES if article["category"] == category),
            KNOWLEDGE_ARTICLES[-1],
        )

    @staticmethod
    def _reasoning(category: str, priority: str, sentiment: str, article_id: str) -> str:
        return (
            f"The message contains signals most consistent with {category.lower()}. "
            f"Impact and timing support a {priority.lower()} priority, while the language reads as "
            f"{sentiment.lower()}. {article_id} supplies the closest demo-policy guidance."
        )

    @staticmethod
    def _next_action(category: str, escalation_needed: bool, status: str) -> str:
        if status == "Resolved":
            return "Send the reviewed reply and keep the ticket available for follow-up"
        if escalation_needed:
            team = {
                "Technical Bug": "engineering and billing",
                "Account Access": "account security",
                "Delivery Issue": "shipping operations",
                "Payment Issue": "billing",
            }.get(category, "a support specialist")
            return f"Route to {team} for human review before sending"
        return "Approve the suggested reply or edit it before sending"

    @staticmethod
    def _draft_reply(ticket: Ticket, category: str, escalation_needed: bool) -> str:
        first_name = ticket.customer.name.split()[0]
        openers = {
            "Delivery Issue": "I’m sorry your delivery is late and that tracking has stopped updating.",
            "Refund Request": "I can help with your return request for the unopened item.",
            "Account Access": "I’m sorry the reset emails have not reached you and that you’re locked out.",
            "Technical Bug": "I’m sorry checkout failed and left duplicate pending charges.",
            "Damaged Product": "I’m sorry the product arrived damaged and understand why you need a safe replacement.",
            "Pricing Question": "Thanks for considering the Business plan for your team.",
        }
        actions = {
            "Delivery Issue": "We’ll check the stalled tracking with the carrier and review the order with our shipping team.",
            "Refund Request": "Because the item is sealed and was ordered last week, it appears eligible for review under the 30-day unopened-item policy. Please reply with the order number.",
            "Account Access": "Please check spam or junk, confirm you’re using the account email, wait ten minutes, and try once more. We’ll then review the lockout securely.",
            "Technical Bug": "Please do not retry payment while the review is active. We’ll trace the checkout error and have billing inspect both pending charges.",
            "Damaged Product": "Please keep the packaging and send photos of the damage if you have not already. We’ll review them for a replacement or refund.",
            "Pricing Question": "Priority support and billing options depend on the current plan configuration, so a sales specialist should confirm the exact terms for 12 seats.",
        }
        escalation = " I’ve flagged this for specialist review before any reply is sent." if escalation_needed else ""
        return f"Hi {first_name},\n\n{openers.get(category, 'Thanks for contacting support.')} {actions.get(category, 'We’ll review the details and confirm the next best step.')}\n\n{escalation}\n\nBest,\nSupport team"

    @staticmethod
    def _polish_reply(draft: str, category: str) -> str:
        suffix = {
            "Delivery Issue": "We won’t promise a delivery date until the carrier check is complete.",
            "Technical Bug": "We won’t mark the ticket resolved until the payment state is verified.",
            "Account Access": "For security, please do not send your password or verification code.",
        }.get(category, "We’ll keep the next step clear and update the ticket after review.")
        return draft.replace("\n\nBest,", f"\n\n{suffix}\n\nBest,")

    def build_demo_tickets(self, rows: list[dict[str, Any]]) -> list[Ticket]:
        results: list[Ticket] = []
        for row in rows:
            created = datetime.fromisoformat(row["created_at"])
            initials = "".join(part[0] for part in row["customer_name"].split()[:2]).upper()
            ticket = Ticket(
                id=row["id"],
                subject=row["subject"],
                message=row["message"],
                customer=Customer(
                    name=row["customer_name"],
                    email=row["customer_email"],
                    plan=row["plan"],
                    initials=initials,
                ),
                channel=row["channel"],
                created_at=created,
                updated_at=created,
            )
            results.append(self._run_demo_workflow(ticket, status_override=row["status"]))
        return results

