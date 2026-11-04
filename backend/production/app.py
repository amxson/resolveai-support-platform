"""Workspace API: explicit transactions, server authorization, no demo fallback."""

import hashlib
import hmac
import logging
import os
import secrets
from contextlib import asynccontextmanager
from typing import Literal
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import create_engine, delete, func, select, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from production.database import (
    Article,
    Audit,
    Invitation,
    Membership,
    Message,
    Organization,
    RateWindow,
    Session,
    Ticket,
    User,
    now,
)

hasher = PasswordHasher()
dummy_hash = hasher.hash(secrets.token_urlsafe(32))
logger = logging.getLogger("resolveai")


def digest(value: str):
    return hashlib.sha256(value.encode()).hexdigest()


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class Signup(Credentials):
    organization: str = Field(min_length=2, max_length=120)


class InviteInput(BaseModel):
    email: EmailStr
    role: Literal["admin", "agent"] = "agent"


class AcceptInput(Credentials):
    token: str = Field(min_length=32, max_length=100)


class TicketInput(BaseModel):
    subject: str = Field(min_length=3, max_length=200)
    customer_email: EmailStr
    message: str = Field(min_length=1, max_length=20000)


class TicketUpdate(BaseModel):
    status: Literal["open", "in_review", "escalated", "resolved"]
    assignee_id: str | None = None


class NoteInput(BaseModel):
    body: str = Field(min_length=1, max_length=20000)


class DraftInput(BaseModel):
    body: str = Field(min_length=1, max_length=20000)
    version: int = Field(ge=0)


class VersionInput(BaseModel):
    version: int = Field(ge=1)


class ArticleInput(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    content: str = Field(min_length=1, max_length=100000)


def create_app(database_url=None, secure_cookies=None, origins=None):
    database_url = database_url or os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required; run Alembic before starting")
    production = os.environ.get("APP_ENV") == "production"
    secure = production if secure_cookies is None else secure_cookies
    allowed = origins or os.environ.get("APP_ORIGINS", "http://localhost:5173").split(
        ","
    )
    if production and (
        not database_url.startswith("postgresql+psycopg://")
        or not secure
        or any(not x.startswith("https://") for x in allowed)
    ):
        raise RuntimeError(
            "Production requires PostgreSQL, secure cookies and HTTPS origins"
        )
    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        **(
            {"connect_args": {"check_same_thread": False}}
            if database_url.startswith("sqlite")
            else {}
        ),
    )
    sessions = sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def lifespan(app):
        yield
        engine.dispose()

    app = FastAPI(title="ResolveAI Workspace API", lifespan=lifespan)
    app.state.engine = engine
    app.state.sessions = sessions
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )

    @app.middleware("http")
    async def security(request, call_next):
        request_id = str(uuid4())
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            # Reject browser cross-origin mutations, including login CSRF.
            origin = request.headers.get("origin")
            if (origin and origin not in allowed) or request.headers.get(
                "sec-fetch-site"
            ) == "cross-site":
                return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
        response = await call_next(request)
        response.headers.update(
            {
                "X-Request-ID": request_id,
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
            }
        )
        if secure:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        logger.info(
            "request", extra={"request_id": request_id, "status": response.status_code}
        )
        return response

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, error):
        logger.error(
            "database operation failed", extra={"error_type": type(error).__name__}
        )
        return JSONResponse(
            {"detail": "Storage temporarily unavailable"}, status_code=503
        )

    def db_session():
        with sessions() as db:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

    def principal(request: Request, db=Depends(db_session, scope="function")):
        session = db.get(Session, digest(request.cookies.get("resolveai_session", "")))
        if not session or session.expires_at <= now():
            raise HTTPException(401, "Sign in required")
        member = db.get(Membership, (session.organization_id, session.user_id))
        if not member:
            raise HTTPException(401, "Membership no longer active")
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if not hmac.compare_digest(
                session.csrf_hash, digest(request.headers.get("x-csrf-token", ""))
            ):
                raise HTTPException(403, "Invalid CSRF token")
        return member

    def admin(member):
        if member.role not in {"owner", "admin"}:
            raise HTTPException(403, "Administrator permission required")

    def audit(db, member, action, resource, **details):
        db.add(
            Audit(
                organization_id=member.organization_id,
                actor_id=member.user_id,
                action=action,
                resource_id=resource,
                details=details,
            )
        )

    def find(db, model, resource_id, member, lock=False):
        query = select(model).where(
            model.id == resource_id, model.organization_id == member.organization_id
        )
        if lock:
            query = query.with_for_update()
        obj = db.scalar(query)
        if obj is None:
            raise HTTPException(404, "Record not found")
        return obj

    def issue_session(db, response, user, org):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        db.add(
            Session(
                token_hash=digest(token),
                csrf_hash=digest(csrf),
                user_id=user.id,
                organization_id=org,
                expires_at=now() + 43200,
            )
        )
        response.set_cookie(
            "resolveai_session",
            token,
            httponly=True,
            secure=secure,
            samesite="lax",
            max_age=43200,
            path="/",
        )
        return {"csrf_token": csrf, "email": user.email, "organization_id": org}

    def auth_limit(request, email):
        # Shared SQL counters; commits separately so failed login cannot erase attempts.
        key = digest(
            f"{request.client.host if request.client else 'unknown'}:{email.lower()}"
        )
        bucket = int(now() // 300)
        key = f"{key}:{bucket}"
        with sessions.begin() as db:
            if engine.dialect.name == "postgresql":
                from sqlalchemy.dialects.postgresql import insert
            else:
                from sqlalchemy.dialects.sqlite import insert
            stmt = insert(RateWindow).values(
                key=key, count=1, reset_at=(bucket + 1) * 300
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[RateWindow.key], set_={"count": RateWindow.count + 1}
            )
            db.execute(stmt)
            count = db.scalar(select(RateWindow.count).where(RateWindow.key == key))
            db.execute(delete(RateWindow).where(RateWindow.reset_at < now() - 300))
        if count > 10:
            raise HTTPException(
                429, "Too many authentication attempts", headers={"Retry-After": "300"}
            )

    @app.get("/health")
    def health():
        return {"status": "alive", "mode": "workspace"}

    @app.get("/ready")
    def ready(db=Depends(db_session, scope="function")):
        db.execute(text("SELECT version_num FROM alembic_version"))
        db.execute(select(User.id).limit(1))
        return {"status": "ready"}

    @app.post("/auth/signup", status_code=201)
    def signup(
        payload: Signup,
        request: Request,
        response: Response,
        db=Depends(db_session, scope="function"),
    ):
        if production and os.environ.get("ALLOW_SIGNUP") != "true":
            raise HTTPException(403, "Public signup is disabled")
        auth_limit(request, payload.email)
        org = Organization(name=payload.organization)
        user = User(
            email=payload.email.lower(), password_hash=hasher.hash(payload.password)
        )
        db.add_all([org, user])
        try:
            db.flush()
        except IntegrityError:
            raise HTTPException(409, "Account cannot be created") from None
        member = Membership(organization_id=org.id, user_id=user.id, role="owner")
        db.add(member)
        audit(db, member, "workspace.created", org.id)
        return issue_session(db, response, user, org.id)

    @app.post("/auth/login")
    def login(
        payload: Credentials,
        request: Request,
        response: Response,
        db=Depends(db_session, scope="function"),
    ):
        auth_limit(request, payload.email)
        user = db.scalar(select(User).where(User.email == payload.email.lower()))
        try:
            hasher.verify(user.password_hash if user else dummy_hash, payload.password)
        except VerificationError:
            raise HTTPException(401, "Invalid credentials") from None
        if not user:
            raise HTTPException(401, "Invalid credentials")
        member = db.scalar(
            select(Membership)
            .where(Membership.user_id == user.id)
            .order_by(Membership.organization_id)
        )
        if not member:
            raise HTTPException(401, "No workspace membership")
        # Rotate this browser's old session after authentication.
        db.execute(
            delete(Session).where(
                Session.token_hash
                == digest(request.cookies.get("resolveai_session", ""))
            )
        )
        return issue_session(db, response, user, member.organization_id)

    @app.get("/auth/me")
    def me(member=Depends(principal), db=Depends(db_session, scope="function")):
        return {
            "email": db.get(User, member.user_id).email,
            "role": member.role,
            "organization": db.get(Organization, member.organization_id).name,
        }

    @app.post("/auth/logout", status_code=204)
    def logout(
        request: Request,
        response: Response,
        member=Depends(principal),
        db=Depends(db_session, scope="function"),
    ):
        db.execute(
            delete(Session).where(
                Session.token_hash
                == digest(request.cookies.get("resolveai_session", ""))
            )
        )
        response.delete_cookie(
            "resolveai_session", path="/", secure=secure, httponly=True, samesite="lax"
        )

    @app.get("/team")
    def team(member=Depends(principal), db=Depends(db_session, scope="function")):
        return [
            {"id": u.id, "email": u.email, "role": m.role}
            for u, m in db.execute(
                select(User, Membership)
                .join(Membership, Membership.user_id == User.id)
                .where(Membership.organization_id == member.organization_id)
            )
        ]

    @app.post("/invitations", status_code=201)
    def invite(
        payload: InviteInput,
        member=Depends(principal),
        db=Depends(db_session, scope="function"),
    ):
        admin(member)
        if payload.role == "admin" and member.role != "owner":
            raise HTTPException(403, "Only owners invite administrators")
        token = secrets.token_urlsafe(32)
        db.add(
            Invitation(
                token_hash=digest(token),
                organization_id=member.organization_id,
                email=payload.email.lower(),
                role=payload.role,
                expires_at=now() + 86400,
            )
        )
        audit(db, member, "invitation.created", digest(token))
        return {
            "token": token,
            "expires_in": 86400,
            "delivery": "Share privately; no email was sent",
        }

    @app.post("/invitations/accept")
    def accept(
        payload: AcceptInput,
        request: Request,
        response: Response,
        db=Depends(db_session, scope="function"),
    ):
        auth_limit(request, payload.email)
        invitation = db.scalar(
            select(Invitation)
            .where(Invitation.token_hash == digest(payload.token))
            .with_for_update()
        )
        if (
            not invitation
            or invitation.expires_at <= now()
            or invitation.email != payload.email.lower()
        ):
            raise HTTPException(400, "Invalid invitation")
        user = db.scalar(select(User).where(User.email == payload.email.lower()))
        if user:
            try:
                hasher.verify(user.password_hash, payload.password)
            except VerificationError:
                raise HTTPException(401, "Invalid credentials") from None
        else:
            user = User(
                email=payload.email.lower(), password_hash=hasher.hash(payload.password)
            )
            db.add(user)
            db.flush()
        if db.get(Membership, (invitation.organization_id, user.id)):
            raise HTTPException(409, "Already a member")
        member = Membership(
            organization_id=invitation.organization_id,
            user_id=user.id,
            role=invitation.role,
        )
        db.add(member)
        audit(db, member, "invitation.accepted", user.id)
        db.delete(invitation)
        return issue_session(db, response, user, member.organization_id)

    @app.delete("/team/{user_id}", status_code=204)
    def remove_member(
        user_id: str,
        member=Depends(principal),
        db=Depends(db_session, scope="function"),
    ):
        admin(member)
        target = db.get(Membership, (member.organization_id, user_id))
        if not target:
            raise HTTPException(404, "Member not found")
        if target.role == "owner" or (
            target.role == "admin" and member.role != "owner"
        ):
            raise HTTPException(403, "Cannot remove this member")
        db.execute(
            update(Ticket)
            .where(
                Ticket.organization_id == member.organization_id,
                Ticket.assignee_id == user_id,
            )
            .values(assignee_id=None)
        )
        db.execute(
            delete(Session).where(
                Session.organization_id == member.organization_id,
                Session.user_id == user_id,
            )
        )
        db.delete(target)
        audit(db, member, "member.removed", user_id)

    @app.get("/tickets")
    def tickets(
        q: str = "",
        status: str | None = None,
        offset: int = 0,
        member=Depends(principal),
        db=Depends(db_session, scope="function"),
    ):
        query = select(Ticket).where(Ticket.organization_id == member.organization_id)
        if len(q) > 200 or offset < 0:
            raise HTTPException(422, "Invalid search")
        if q:
            query = query.where(Ticket.subject.contains(q, autoescape=True))
        if status:
            query = query.where(Ticket.status == status)
        return list(
            db.scalars(
                query.order_by(Ticket.created_at.desc()).offset(offset).limit(100)
            )
        )

    @app.post("/tickets", status_code=201)
    def new_ticket(
        payload: TicketInput,
        member=Depends(principal),
        db=Depends(db_session, scope="function"),
    ):
        ticket = Ticket(
            organization_id=member.organization_id,
            subject=payload.subject,
            customer_email=payload.customer_email.lower(),
        )
        db.add(ticket)
        db.flush()
        db.add(
            Message(
                organization_id=member.organization_id,
                ticket_id=ticket.id,
                kind="incoming",
                body=payload.message,
            )
        )
        audit(db, member, "ticket.created", ticket.id)
        return ticket

    @app.get("/tickets/{ticket_id}")
    def ticket_detail(
        ticket_id: str,
        member=Depends(principal),
        db=Depends(db_session, scope="function"),
    ):
        ticket = find(db, Ticket, ticket_id, member)
        messages = list(
            db.scalars(
                select(Message)
                .where(
                    Message.organization_id == member.organization_id,
                    Message.ticket_id == ticket_id,
                )
                .order_by(Message.created_at)
            )
        )
        return {"ticket": ticket, "messages": messages}

    @app.patch("/tickets/{ticket_id}")
    def edit_ticket(
        ticket_id: str,
        payload: TicketUpdate,
        member=Depends(principal),
        db=Depends(db_session, scope="function"),
    ):
        ticket = find(db, Ticket, ticket_id, member, True)
        if payload.assignee_id and not db.get(
            Membership, (member.organization_id, payload.assignee_id)
        ):
            raise HTTPException(422, "Assignee must belong to workspace")
        ticket.status, ticket.assignee_id = payload.status, payload.assignee_id
        audit(
            db,
            member,
            "ticket.updated",
            ticket.id,
            status=payload.status,
            assignee_id=payload.assignee_id,
        )
        return ticket

    @app.post("/tickets/{ticket_id}/notes", status_code=201)
    def note(
        ticket_id: str,
        payload: NoteInput,
        member=Depends(principal),
        db=Depends(db_session, scope="function"),
    ):
        find(db, Ticket, ticket_id, member)
        record = Message(
            organization_id=member.organization_id,
            ticket_id=ticket_id,
            kind="internal",
            body=payload.body,
        )
        db.add(record)
        audit(db, member, "note.created", ticket_id)
        db.flush()
        return record

    @app.put("/tickets/{ticket_id}/draft")
    def draft(
        ticket_id: str,
        payload: DraftInput,
        member=Depends(principal),
        db=Depends(db_session, scope="function"),
    ):
        find(db, Ticket, ticket_id, member)
        result = db.execute(
            update(Ticket)
            .where(
                Ticket.id == ticket_id,
                Ticket.organization_id == member.organization_id,
                Ticket.draft_version == payload.version,
            )
            .values(
                draft=payload.body,
                draft_version=payload.version + 1,
                approved_version=None,
            )
        )
        if result.rowcount != 1:
            raise HTTPException(409, "Draft changed; reload before saving")
        audit(db, member, "draft.saved", ticket_id, version=payload.version + 1)
        return {"version": payload.version + 1}

    @app.post("/tickets/{ticket_id}/approve")
    def approve(
        ticket_id: str,
        payload: VersionInput,
        member=Depends(principal),
        db=Depends(db_session, scope="function"),
    ):
        find(db, Ticket, ticket_id, member)
        result = db.execute(
            update(Ticket)
            .where(
                Ticket.id == ticket_id,
                Ticket.organization_id == member.organization_id,
                Ticket.draft_version == payload.version,
                Ticket.draft != "",
            )
            .values(approved_version=payload.version)
        )
        if result.rowcount != 1:
            raise HTTPException(409, "Draft changed or empty")
        audit(db, member, "draft.approved", ticket_id, version=payload.version)
        return {"approved_version": payload.version, "sent": False}

    @app.post("/tickets/{ticket_id}/reject", status_code=204)
    def reject(
        ticket_id: str,
        member=Depends(principal),
        db=Depends(db_session, scope="function"),
    ):
        ticket = find(db, Ticket, ticket_id, member, True)
        ticket.approved_version = None
        audit(db, member, "draft.rejected", ticket_id)

    @app.get("/knowledge")
    def knowledge(member=Depends(principal), db=Depends(db_session, scope="function")):
        return list(
            db.scalars(
                select(Article)
                .where(Article.organization_id == member.organization_id)
                .limit(100)
            )
        )

    @app.post("/knowledge", status_code=201)
    def add_article(
        payload: ArticleInput,
        member=Depends(principal),
        db=Depends(db_session, scope="function"),
    ):
        admin(member)
        article = Article(
            organization_id=member.organization_id, **payload.model_dump()
        )
        db.add(article)
        db.flush()
        audit(db, member, "article.created", article.id)
        return article

    @app.put("/knowledge/{article_id}")
    def edit_article(
        article_id: str,
        payload: ArticleInput,
        member=Depends(principal),
        db=Depends(db_session, scope="function"),
    ):
        admin(member)
        article = find(db, Article, article_id, member, True)
        article.title, article.content = payload.title, payload.content
        article.version += 1
        audit(db, member, "article.updated", article.id, version=article.version)
        return article

    @app.delete("/knowledge/{article_id}", status_code=204)
    def delete_article(
        article_id: str,
        member=Depends(principal),
        db=Depends(db_session, scope="function"),
    ):
        admin(member)
        db.delete(find(db, Article, article_id, member, True))
        audit(db, member, "article.deleted", article_id)

    @app.get("/audit")
    def history(member=Depends(principal), db=Depends(db_session, scope="function")):
        return list(
            db.scalars(
                select(Audit)
                .where(Audit.organization_id == member.organization_id)
                .order_by(Audit.created_at.desc())
                .limit(100)
            )
        )

    @app.get("/analytics")
    def analytics(member=Depends(principal), db=Depends(db_session, scope="function")):
        counts = dict(
            db.execute(
                select(Ticket.status, func.count())
                .where(Ticket.organization_id == member.organization_id)
                .group_by(Ticket.status)
            ).all()
        )
        return {
            "total_tickets": sum(counts.values()),
            "by_status": counts,
            "ai_processing": "not_configured",
            "email_delivery": "not_configured",
        }

    return app
