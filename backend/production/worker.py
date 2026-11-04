"""Durable leased analysis jobs. Start with python -m production.worker."""

import os
import time
from uuid import uuid4

from sqlalchemy import create_engine, or_, select, update
from sqlalchemy.orm import sessionmaker

from production.ai import analyze
from production.database import AnalysisJob, Article, Audit, Message, Ticket, now


def run_once(sessions, processor=analyze):
    lease = str(uuid4())
    with sessions.begin() as db:
        candidate = db.scalar(
            select(AnalysisJob)
            .where(
                AnalysisJob.available_at <= now(),
                or_(
                    AnalysisJob.status == "pending",
                    (AnalysisJob.status == "running")
                    & (AnalysisJob.lease_until < now()),
                ),
            )
            .order_by(AnalysisJob.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not candidate:
            return False
        if candidate.attempts >= 3:
            candidate.status = "failed"
            candidate.error = "LeaseExpired"
            db.execute(
                update(Ticket)
                .where(
                    Ticket.id == candidate.ticket_id,
                    Ticket.organization_id == candidate.organization_id,
                )
                .values(status="escalated")
            )
            db.add(
                Audit(
                    organization_id=candidate.organization_id,
                    actor_id=candidate.actor_id,
                    action="analysis.error",
                    resource_id=candidate.ticket_id,
                    details={"job_id": candidate.id, "error": "LeaseExpired"},
                )
            )
            return True
        # CAS also protects SQLite local workers, where row locks aren't available.
        result = db.execute(
            update(AnalysisJob)
            .where(AnalysisJob.id == candidate.id, AnalysisJob.lease_until < now())
            .values(
                status="running",
                lease=lease,
                lease_until=now() + 120,
                attempts=AnalysisJob.attempts + 1,
            )
        )
        if result.rowcount != 1:
            return False
        job_id = candidate.id
    try:
        with sessions() as db:
            job = db.get(AnalysisJob, job_id)
            ticket = db.scalar(
                select(Ticket).where(
                    Ticket.id == job.ticket_id,
                    Ticket.organization_id == job.organization_id,
                )
            )
            if not ticket:
                raise ValueError("ticket_deleted")
            messages = list(
                db.scalars(
                    select(Message)
                    .where(
                        Message.ticket_id == ticket.id,
                        Message.organization_id == job.organization_id,
                    )
                    .order_by(Message.created_at)
                )
            )
            articles = list(
                db.scalars(
                    select(Article)
                    .where(Article.organization_id == job.organization_id)
                    .limit(100)
                )
            )
            output = processor(ticket.subject, messages, articles)
        with sessions.begin() as db:
            job = db.scalar(
                select(AnalysisJob)
                .where(AnalysisJob.id == job_id, AnalysisJob.lease == lease)
                .with_for_update()
            )
            if not job or job.lease_until < now():
                return True
            result = db.execute(
                update(Ticket)
                .where(
                    Ticket.id == job.ticket_id,
                    Ticket.organization_id == job.organization_id,
                    Ticket.draft_version == job.draft_version,
                )
                .values(
                    draft=output["draft"],
                    draft_version=job.draft_version + 1,
                    approved_version=None,
                    status="escalated" if output["escalate"] else "in_review",
                )
            )
            job.status = "completed" if result.rowcount == 1 else "conflict"
            job.result = output
            db.add(
                Audit(
                    organization_id=job.organization_id,
                    actor_id=job.actor_id,
                    action=f"analysis.{job.status}",
                    resource_id=job.ticket_id,
                    details={
                        "job_id": job.id,
                        "provider_called": output.get("provider_called", False),
                    },
                )
            )
    except Exception as error:
        with sessions.begin() as db:
            job = db.scalar(
                select(AnalysisJob)
                .where(AnalysisJob.id == job_id, AnalysisJob.lease == lease)
                .with_for_update()
            )
            if job:
                # Store only a safe error class, never a provider body or API URL/key.
                job.error = type(error).__name__
                job.status = "failed" if job.attempts >= 3 else "pending"
                job.available_at = now() + 30 * (2 ** (job.attempts - 1))
                job.lease_until = 0
                if job.status == "failed":
                    db.execute(
                        update(Ticket)
                        .where(
                            Ticket.id == job.ticket_id,
                            Ticket.organization_id == job.organization_id,
                        )
                        .values(status="escalated")
                    )
                db.add(
                    Audit(
                        organization_id=job.organization_id,
                        actor_id=job.actor_id,
                        action="analysis.error",
                        resource_id=job.ticket_id,
                        details={"job_id": job.id, "error": job.error},
                    )
                )
    return True


if __name__ == "__main__":
    engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    sessions = sessionmaker(engine, expire_on_commit=False)
    while True:
        if not run_once(sessions):
            time.sleep(2)
