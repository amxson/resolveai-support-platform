"""API models shared by ticket, workflow, and analytics endpoints."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class TicketStatus(str, Enum):
    NEW = "New"
    IN_REVIEW = "In Review"
    ESCALATED = "Escalated"
    RESOLVED = "Resolved"


class Priority(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    URGENT = "Urgent"


class Sentiment(str, Enum):
    POSITIVE = "Positive"
    NEUTRAL = "Neutral"
    FRUSTRATED = "Frustrated"
    NEGATIVE = "Negative"


class AgentStep(BaseModel):
    name: str
    role: str
    status: str = "Completed"
    summary: str
    confidence: int = Field(ge=0, le=100)
    duration_ms: int = Field(ge=0)


class Customer(BaseModel):
    name: str
    email: EmailStr
    plan: str = "Starter"
    initials: str


class KnowledgeMatch(BaseModel):
    article_id: str
    title: str
    excerpt: str
    score: int = Field(ge=0, le=100)
    section: str


class QualityReview(BaseModel):
    status: str
    score: int = Field(ge=0, le=100)
    checks: list[str]
    notes: str


class TicketCreate(BaseModel):
    subject: str = Field(min_length=4, max_length=140)
    message: str = Field(min_length=10, max_length=5000)
    customer_name: str = Field(min_length=2, max_length=100)
    customer_email: EmailStr
    channel: str = "Email"


class Ticket(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: str
    subject: str
    message: str
    customer: Customer
    channel: str = "Email"
    created_at: datetime
    updated_at: datetime
    category: str = "Unclassified"
    priority: Priority = Priority.MEDIUM
    sentiment: Sentiment = Sentiment.NEUTRAL
    status: TicketStatus = TicketStatus.NEW
    confidence: int = Field(default=0, ge=0, le=100)
    escalation_needed: bool = False
    suggested_next_action: str = "Run AI analysis"
    reasoning_summary: str = "Waiting for the prototype workflow to analyze this ticket."
    knowledge_match: KnowledgeMatch | None = None
    draft_response: str = ""
    final_response: str = ""
    quality_review: QualityReview | None = None
    agent_steps: list[AgentStep] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class TicketList(BaseModel):
    items: list[Ticket]
    total: int


class KnowledgeArticle(BaseModel):
    id: str
    title: str
    category: str
    summary: str
    content: str
    updated_at: str
    usage_count: int


class Analytics(BaseModel):
    total_tickets: int
    urgent_tickets: int
    resolved_tickets: int
    average_confidence: int
    resolution_rate: int
    average_first_response_minutes: int
    by_status: dict[str, int]
    by_priority: dict[str, int]
    by_category: dict[str, int]
    weekly_volume: list[dict[str, int | str]]


class HealthResponse(BaseModel):
    status: str
    mode: str
    version: str
    ai_provider_configured: bool
    message: str

