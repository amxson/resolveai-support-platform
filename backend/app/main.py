"""FastAPI entry point for ResolveAI Support Platform."""

from collections import Counter

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.data import DEMO_TICKETS, KNOWLEDGE_ARTICLES
from app.models import (
    Analytics,
    HealthResponse,
    KnowledgeArticle,
    Ticket,
    TicketCreate,
    TicketList,
)
from app.services.store import TicketStore
from app.services.workflow import WorkflowService


settings = get_settings()
workflow = WorkflowService(settings)
store = TicketStore(workflow.build_demo_tickets(DEMO_TICKETS))

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Portfolio prototype API demonstrating multi-agent customer support automation. "
        "All bundled tickets and policies are fictional demo data."
    ),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_ticket(ticket_id: str) -> Ticket:
    ticket = store.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} was not found")
    return ticket


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "docs": "/docs",
        "disclaimer": "Portfolio prototype with fictional demo data; not a live company system.",
    }


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        mode=workflow.mode,
        version=settings.app_version,
        ai_provider_configured=bool(settings.gemini_api_key),
        message=(
            "Deterministic demo workflow is active; no external API key is required."
            if workflow.mode == "Demo"
            else "CrewAI mode is active with a configured Gemini provider."
        ),
    )


@app.get("/tickets", response_model=TicketList)
def list_tickets(
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    category: str | None = Query(default=None),
) -> TicketList:
    tickets = store.list()
    if status:
        tickets = [ticket for ticket in tickets if ticket.status.lower() == status.lower()]
    if priority:
        tickets = [ticket for ticket in tickets if ticket.priority.lower() == priority.lower()]
    if category:
        tickets = [ticket for ticket in tickets if ticket.category.lower() == category.lower()]
    return TicketList(items=tickets, total=len(tickets))


@app.post("/tickets", response_model=Ticket, status_code=201)
def create_ticket(payload: TicketCreate) -> Ticket:
    ticket = workflow.create_ticket(store.next_id(), payload)
    return store.save(ticket)


@app.get("/tickets/{ticket_id}", response_model=Ticket)
def get_ticket(ticket_id: str) -> Ticket:
    return require_ticket(ticket_id)


@app.post("/tickets/{ticket_id}/analyze", response_model=Ticket)
def analyze_ticket(ticket_id: str) -> Ticket:
    ticket = require_ticket(ticket_id)
    try:
        return store.save(workflow.analyze(ticket))
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Analysis workflow failed: {error}") from error


@app.post("/tickets/{ticket_id}/generate-response", response_model=Ticket)
def generate_response(ticket_id: str) -> Ticket:
    ticket = require_ticket(ticket_id)
    if not ticket.final_response:
        ticket = workflow.analyze(ticket)
    return store.save(ticket)


@app.get("/knowledge-base", response_model=list[KnowledgeArticle])
def knowledge_base() -> list[KnowledgeArticle]:
    return [KnowledgeArticle(**article) for article in KNOWLEDGE_ARTICLES]


@app.get("/analytics", response_model=Analytics)
def analytics() -> Analytics:
    tickets = store.list()
    by_status = Counter(ticket.status for ticket in tickets)
    by_priority = Counter(ticket.priority for ticket in tickets)
    by_category = Counter(ticket.category for ticket in tickets)
    resolved = by_status.get("Resolved", 0)
    urgent = sum(ticket.priority in {"High", "Urgent"} for ticket in tickets)
    average_confidence = round(sum(ticket.confidence for ticket in tickets) / len(tickets))
    return Analytics(
        total_tickets=len(tickets),
        urgent_tickets=urgent,
        resolved_tickets=resolved,
        average_confidence=average_confidence,
        resolution_rate=round(resolved / len(tickets) * 100),
        average_first_response_minutes=4,
        by_status=dict(by_status),
        by_priority=dict(by_priority),
        by_category=dict(by_category),
        weekly_volume=[
            {"day": "Mon", "tickets": 14, "resolved": 10},
            {"day": "Tue", "tickets": 19, "resolved": 15},
            {"day": "Wed", "tickets": 17, "resolved": 14},
            {"day": "Thu", "tickets": 24, "resolved": 18},
            {"day": "Fri", "tickets": 21, "resolved": 17},
            {"day": "Sat", "tickets": 11, "resolved": 9},
            {"day": "Sun", "tickets": 8, "resolved": 7},
        ],
    )

