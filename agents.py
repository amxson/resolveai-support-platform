"""Agent definitions for the customer support ticket workflow."""

from __future__ import annotations

import os
from pathlib import Path

from crewai import Agent, LLM
from dotenv import load_dotenv

from tools.knowledge_base_tool import KnowledgeBaseSearchTool


load_dotenv(Path(__file__).resolve().parent / ".env")

gemini_api_key = os.getenv("GEMINI_API_KEY")
gemini_model = os.getenv("GEMINI_MODEL", "gemini/gemini-2.0-flash")

llm = LLM(
    model=gemini_model,
    api_key=gemini_api_key,
    temperature=0.2,
    max_tokens=2000,
)


def create_ticket_triage_agent() -> Agent:
    """Create the agent that classifies tickets and decides priority."""
    return Agent(
        role="Ticket Triage Agent",
        goal=(
            "Classify each customer support ticket into exactly one approved "
            "category, assign a priority, and decide whether escalation is needed."
        ),
        backstory=(
            "You are a support operations specialist. You read customer messages "
            "carefully, identify the core issue, and route work accurately using "
            "only the supported category list."
        ),
        llm=llm,
        allow_delegation=False,
        verbose=False,
    )


def create_knowledge_base_agent() -> Agent:
    """Create the agent that searches local support policies."""
    return Agent(
        role="Knowledge Base Agent",
        goal=(
            "Find the most relevant local support policy for a classified "
            "customer support ticket."
        ),
        backstory=(
            "You know the company's support policies and use the local "
            "knowledge base instead of web search."
        ),
        tools=[KnowledgeBaseSearchTool()],
        llm=llm,
        allow_delegation=False,
        verbose=False,
    )


def create_response_writer_agent() -> Agent:
    """Create the agent that writes the customer-facing reply."""
    return Agent(
        role="Response Writer Agent",
        goal=(
            "Write polite, helpful, professional customer support replies "
            "using the ticket details and relevant policy."
        ),
        backstory=(
            "You are an experienced customer support representative who writes "
            "clear replies that are empathetic, accurate, and easy to act on."
        ),
        llm=llm,
        allow_delegation=False,
        verbose=False,
    )


def create_quality_checker_agent() -> Agent:
    """Create the agent that reviews and approves the final response."""
    return Agent(
        role="Quality Checker Agent",
        goal=(
            "Review support replies for politeness, correctness, policy "
            "alignment, missing information, and escalation decisions."
        ),
        backstory=(
            "You are a senior support quality analyst. You make sure every "
            "customer reply is accurate, complete, and aligned with policy."
        ),
        llm=llm,
        allow_delegation=False,
        verbose=False,
    )
