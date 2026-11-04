"""Small encrypted database-backed files; no public URLs or local filesystem paths."""

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote, unquote

from cryptography.fernet import Fernet, MultiFernet
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import func, select

from production.database import Article, Organization, StoredFile, Ticket

MAX_SIZE = 5 * 1024 * 1024
TYPES = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


def file_cipher():
    values = os.environ.get("FILE_ENCRYPTION_KEY", "")
    if not values:
        raise HTTPException(503, "File storage encryption is not configured")
    return MultiFernet([Fernet(key.strip().encode()) for key in values.split(",")])


def clean_file(filename, payload):
    filename = unquote(filename).replace("\\", "/").split("/")[-1]
    filename = "".join(c for c in filename if c.isprintable())[:200]
    suffix = Path(filename).suffix.lower()
    if not filename or suffix not in TYPES or len(payload) > MAX_SIZE or not payload:
        raise HTTPException(
            422, "Use a nonempty PDF, TXT, Markdown, PNG or JPEG file up to 5 MB"
        )
    if suffix == ".pdf" and not payload.startswith(b"%PDF-"):
        raise HTTPException(422, "Invalid PDF signature")
    if suffix == ".png" and not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(422, "Invalid PNG signature")
    if suffix in {".jpg", ".jpeg"} and not payload.startswith(b"\xff\xd8\xff"):
        raise HTTPException(422, "Invalid JPEG signature")
    return filename, TYPES[suffix]


def extract_document(filename, payload):
    suffix = Path(filename).suffix.lower()
    if suffix not in {".txt", ".md", ".pdf"}:
        raise HTTPException(422, "Knowledge documents support PDF, TXT and Markdown")
    try:
        if suffix == ".pdf":
            result = subprocess.run(
                [sys.executable, str(Path(__file__).with_name("pdf_text.py"))],
                input=payload,
                capture_output=True,
                timeout=10,
                check=True,
            )
            content = result.stdout.decode("utf-8")
        else:
            content = payload.decode("utf-8-sig")
        if not content.strip() or len(content) > 100000 or "\x00" in content:
            raise ValueError("Invalid text")
        return content
    except (ValueError, UnicodeError, subprocess.SubprocessError):
        raise HTTPException(
            422,
            "Document could not be safely parsed; use readable UTF-8 text or a text-based PDF up to 100 pages",
        ) from None


async def upload(request):
    data = bytearray()
    async for block in request.stream():
        data.extend(block)
        if len(data) > MAX_SIZE:
            raise HTTPException(413, "File exceeds 5 MB")
    filename, content_type = clean_file(
        request.headers.get("x-filename", ""), bytes(data)
    )
    return filename, content_type, bytes(data)


def store_file(
    db, member, filename, content_type, payload, ticket_id=None, article_id=None
):
    db.scalar(
        select(Organization)
        .where(Organization.id == member.organization_id)
        .with_for_update(key_share=True)
    )
    size = db.scalar(
        select(func.coalesce(func.sum(StoredFile.size), 0)).where(
            StoredFile.organization_id == member.organization_id
        )
    )
    if size + len(payload) > 50 * 1024 * 1024:
        raise HTTPException(413, "Workspace file storage limit is 50 MB")
    record = StoredFile(
        organization_id=member.organization_id,
        ticket_id=ticket_id,
        article_id=article_id,
        filename=filename,
        content_type=content_type,
        size=len(payload),
        encrypted_data=file_cipher().encrypt(payload).decode(),
    )
    db.add(record)
    db.flush()
    return {
        "id": record.id,
        "filename": filename,
        "content_type": content_type,
        "size": len(payload),
    }


def register(app, principal, db_session, find, admin, audit):
    @app.post("/tickets/{ticket_id}/attachments", status_code=201)
    async def attach(
        ticket_id: str,
        request: Request,
        member=Depends(principal),
        db=Depends(db_session, scope="function"),
    ):
        find(db, Ticket, ticket_id, member, True)
        filename, content_type, payload = await upload(request)
        result = store_file(
            db, member, filename, content_type, payload, ticket_id=ticket_id
        )
        audit(db, member, "attachment.created", result["id"])
        return result

    @app.get("/tickets/{ticket_id}/attachments")
    def attachments(
        ticket_id: str,
        member=Depends(principal),
        db=Depends(db_session, scope="function"),
    ):
        find(db, Ticket, ticket_id, member)
        return [
            {
                "id": f.id,
                "filename": f.filename,
                "content_type": f.content_type,
                "size": f.size,
            }
            for f in db.scalars(
                select(StoredFile).where(
                    StoredFile.organization_id == member.organization_id,
                    StoredFile.ticket_id == ticket_id,
                )
            )
        ]

    @app.get("/files/{file_id}")
    def download(
        file_id: str,
        member=Depends(principal),
        db=Depends(db_session, scope="function"),
    ):
        record = find(db, StoredFile, file_id, member)
        return Response(
            file_cipher().decrypt(record.encrypted_data.encode()),
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": "attachment; filename*=UTF-8''"
                + quote(record.filename, safe=""),
                "X-Content-Type-Options": "nosniff",
            },
        )

    @app.delete("/files/{file_id}", status_code=204)
    def remove(
        file_id: str,
        member=Depends(principal),
        db=Depends(db_session, scope="function"),
    ):
        record = find(db, StoredFile, file_id, member, True)
        if record.article_id:
            admin(member)
        db.delete(record)
        audit(db, member, "file.deleted", file_id)

    @app.post("/knowledge/documents", status_code=201)
    async def document(
        request: Request,
        member=Depends(principal),
        db=Depends(db_session, scope="function"),
    ):
        admin(member)
        filename, content_type, payload = await upload(request)
        content = await asyncio.to_thread(extract_document, filename, payload)
        if (
            db.scalar(
                select(func.count())
                .select_from(Article)
                .where(Article.organization_id == member.organization_id)
            )
            >= 100
        ):
            raise HTTPException(409, "Workspace knowledge limit is 100 articles")
        article = Article(
            organization_id=member.organization_id, title=filename, content=content
        )
        db.add(article)
        db.flush()
        result = store_file(
            db, member, filename, content_type, payload, article_id=article.id
        )
        audit(db, member, "document.ingested", article.id, file_id=result["id"])
        return {"article_id": article.id, "version": article.version, "file": result}
