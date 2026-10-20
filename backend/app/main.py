"""FastAPI entry point for ResolveAI Support Platform."""

from collections import Counter, deque
from threading import Lock, BoundedSemaphore
from time import monotonic
import hmac
import logging
from contextlib import contextmanager

from fastapi import FastAPI, HTTPException, Query, Depends, Header, Request
from fastapi.responses import JSONResponse
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
from app.services.store import TicketStore, StoreFullError
from app.services.workflow import WorkflowService

settings = get_settings()
workflow = WorkflowService(settings)
store = TicketStore(workflow.build_demo_tickets(DEMO_TICKETS), settings.max_tickets)
write_times = deque()
write_lock = Lock()
analysis_slots = BoundedSemaphore(2)
logger = logging.getLogger(__name__)

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
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.exception_handler(StoreFullError)
async def store_full(request: Request, error: StoreFullError):
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Demo ticket capacity reached. Try again after the service resets."
        },
    )


def guard_write(authorization: str | None = Header(default=None)) -> None:
    # Public demo writes stay usable; paid-provider calls require an operator token.
    if workflow.mode == "CrewAI" or settings.api_token:
        expected = f"Bearer {settings.api_token}"
        if not settings.api_token or not hmac.compare_digest(
            (authorization or "").encode(), expected.encode()
        ):
            raise HTTPException(
                status_code=401,
                detail="Operator authentication required.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    with write_lock:
        now = monotonic()
        while write_times and write_times[0] <= now - 60:
            write_times.popleft()
        if len(write_times) >= settings.writes_per_minute:
            raise HTTPException(
                status_code=429,
                detail="Demo write limit reached.",
                headers={"Retry-After": "60"},
            )
        write_times.append(now)


@contextmanager
def analysis_slot():
    if not analysis_slots.acquire(blocking=False):
        raise HTTPException(
            status_code=503, detail="Analysis is busy. Try again shortly."
        )
    try:
        yield
    finally:
        analysis_slots.release()


def analyze_safely(ticket: Ticket) -> Ticket:
    with analysis_slot():
        try:
            return workflow.analyze(ticket)
        except Exception as error:
            logger.warning("Ticket analysis failed (%s)", type(error).__name__)
            raise HTTPException(
                status_code=502, detail="Analysis service unavailable. Try again later."
            ) from error


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
        tickets = [
            ticket for ticket in tickets if ticket.status.lower() == status.lower()
        ]
    if priority:
        tickets = [
            ticket for ticket in tickets if ticket.priority.lower() == priority.lower()
        ]
    if category:
        tickets = [
            ticket for ticket in tickets if ticket.category.lower() == category.lower()
        ]
    return TicketList(items=tickets, total=len(tickets))


@app.post(
    "/tickets",
    response_model=Ticket,
    status_code=201,
    dependencies=[Depends(guard_write)],
)
def create_ticket(payload: TicketCreate) -> Ticket:
    store.ensure_capacity()
    ticket = workflow.create_ticket(store.next_id(), payload)
    return store.save(analyze_safely(ticket))


@app.get("/tickets/{ticket_id}", response_model=Ticket)
def get_ticket(ticket_id: str) -> Ticket:
    return require_ticket(ticket_id)


@app.post(
    "/tickets/{ticket_id}/analyze",
    response_model=Ticket,
    dependencies=[Depends(guard_write)],
)
def analyze_ticket(ticket_id: str) -> Ticket:
    ticket = require_ticket(ticket_id)
    return store.save(analyze_safely(ticket))


@app.post(
    "/tickets/{ticket_id}/generate-response",
    response_model=Ticket,
    dependencies=[Depends(guard_write)],
)
def generate_response(ticket_id: str) -> Ticket:
    ticket = require_ticket(ticket_id)
    if not ticket.final_response:
        ticket = analyze_safely(ticket)
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
    average_confidence = round(
        sum(ticket.confidence for ticket in tickets) / max(1, len(tickets))
    )
    return Analytics(
        total_tickets=len(tickets),
        urgent_tickets=urgent,
        resolved_tickets=resolved,
        average_confidence=average_confidence,
        resolution_rate=round(resolved / max(1, len(tickets)) * 100),
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
