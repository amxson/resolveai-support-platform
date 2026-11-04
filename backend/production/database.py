"""Persistent schema shared by migrations and the authenticated API."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uid():
    return str(uuid4())


def now():
    return datetime.now(UTC).timestamp()


class Base(DeclarativeBase):
    pass


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(120))


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)


class Membership(Base):
    __tablename__ = "memberships"
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(12))


class Session(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"))
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[float]


class Invitation(Base):
    __tablename__ = "invitations"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"))
    email: Mapped[str] = mapped_column(String(254))
    role: Mapped[str] = mapped_column(String(12))
    expires_at: Mapped[float]


class Ticket(Base):
    __tablename__ = "support_tickets"
    __table_args__ = (UniqueConstraint("organization_id", "id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    subject: Mapped[str] = mapped_column(String(200))
    customer_email: Mapped[str] = mapped_column(String(254))
    status: Mapped[str] = mapped_column(String(20), default="open")
    assignee_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    draft: Mapped[str] = mapped_column(Text, default="")
    draft_version: Mapped[int] = mapped_column(default=0)
    approved_version: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[float] = mapped_column(default=now)


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    ticket_id: Mapped[str] = mapped_column(ForeignKey("support_tickets.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[float] = mapped_column(default=now)


class Article(Base):
    __tablename__ = "articles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(default=1)


class Audit(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[str] = mapped_column(String(80))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[float] = mapped_column(default=now)


class RateWindow(Base):
    __tablename__ = "rate_windows"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    count: Mapped[int] = mapped_column(default=0)
    reset_at: Mapped[float]
