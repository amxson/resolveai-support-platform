"""Optional five-agent CrewAI execution path used when demo mode is disabled."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from app.config import Settings
from app.models import AgentStep, KnowledgeMatch, QualityReview, Ticket


def _extract_json(raw: str) -> dict:
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        raise ValueError("CrewAI result did not contain a JSON object")
    return json.loads(match.group(0))


def run_crewai_workflow(ticket: Ticket, settings: Settings) -> Ticket:
    """Run a real CrewAI sequence and normalize its structured final decision."""
    from crewai import Agent, Crew, LLM, Process, Task

    llm = LLM(
        model=settings.gemini_model,
        api_key=settings.gemini_api_key,
        temperature=0.2,
        max_tokens=2500,
    )
    roles = [
        ("Triage Agent", "Classify category, priority, urgency, and sentiment."),
        ("Knowledge Base Agent", "Select the most relevant provided policy article."),
        ("Response Writer Agent", "Draft an empathetic and policy-grounded response."),
        ("Quality Review Agent", "Check tone, safety, accuracy, and unsupported promises."),
        ("Decision Agent", "Choose escalation, status, confidence, and the final next action."),
    ]
    agents = [
        Agent(
            role=role,
            goal=goal,
            backstory="You are part of a portfolio prototype; never imply real-world company deployment.",
            llm=llm,
            allow_delegation=False,
            verbose=False,
        )
        for role, goal in roles
    ]
    policy_context = (
        "KB-001 delivery delays; KB-002 refunds; KB-003 account recovery; "
        "KB-004 checkout and duplicate charges; KB-005 damaged products; KB-006 pricing."
    )
    tasks: list[Task] = []
    instructions = [
        f"Analyze ticket {ticket.id}: {ticket.message}",
        f"Use this demo knowledge index: {policy_context}",
        "Draft a helpful reply based on the prior outputs. Do not invent policy or resolution times.",
        "Review the draft and correct it. Preserve human approval before sending.",
        (
            "Return only JSON with keys: category, priority, sentiment, status, confidence, "
            "escalation_needed, suggested_next_action, reasoning_summary, article_id, article_title, "
            "article_excerpt, article_score, draft_response, final_response, quality_score, quality_notes."
        ),
    ]
    for index, (agent, description) in enumerate(zip(agents, instructions)):
        tasks.append(
            Task(
                description=description,
                expected_output="A concise stage result." if index < 4 else "One valid JSON object.",
                agent=agent,
                context=tasks.copy(),
            )
        )
    result = Crew(agents=agents, tasks=tasks, process=Process.sequential, verbose=False).kickoff()
    payload = _extract_json(str(getattr(result, "raw", result)))
    confidence = max(0, min(100, int(payload.get("confidence", 85))))
    article_score = max(0, min(100, int(payload.get("article_score", confidence))))
    quality_score = max(0, min(100, int(payload.get("quality_score", confidence))))
    steps = [
        AgentStep(
            name=role,
            role=goal,
            summary="Completed by the configured CrewAI workflow.",
            confidence=confidence,
            duration_ms=0,
        )
        for role, goal in roles
    ]
    return ticket.model_copy(
        update={
            "category": payload.get("category", "General Question"),
            "priority": payload.get("priority", "Medium"),
            "sentiment": payload.get("sentiment", "Neutral"),
            "status": payload.get("status", "In Review"),
            "confidence": confidence,
            "escalation_needed": bool(payload.get("escalation_needed", False)),
            "suggested_next_action": payload.get("suggested_next_action", "Human review"),
            "reasoning_summary": payload.get("reasoning_summary", "CrewAI analysis completed."),
            "knowledge_match": KnowledgeMatch(
                article_id=payload.get("article_id", "KB-006"),
                title=payload.get("article_title", "General support guidance"),
                excerpt=payload.get("article_excerpt", "Review applicable support guidance."),
                score=article_score,
                section=payload.get("category", "General Question"),
            ),
            "draft_response": payload.get("draft_response", ""),
            "final_response": payload.get("final_response", ""),
            "quality_review": QualityReview(
                status="Reviewed by CrewAI",
                score=quality_score,
                checks=["Tone", "Policy alignment", "Unsupported promises", "Next action"],
                notes=payload.get("quality_notes", "Review completed."),
            ),
            "agent_steps": steps,
            "updated_at": datetime.now(timezone.utc),
        }
    )

