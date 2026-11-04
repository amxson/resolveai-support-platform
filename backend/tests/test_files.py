import io

import pytest
from cryptography.fernet import Fernet
from pypdf import PdfWriter
from sqlalchemy import select
from test_workspace import account, ticket

from production.database import StoredFile


def test_file_encryption_download_tenant_boundary_and_deletion(
    application, monkeypatch
):
    monkeypatch.setenv("FILE_ENCRYPTION_KEY", Fernet.generate_key().decode())
    owner = account(application)
    other = account(application, "other@example.com")
    tid = ticket(owner)
    payload = b"Private attachment text"
    response = owner.post(
        f"/tickets/{tid}/attachments",
        content=payload,
        headers={
            "X-Filename": "../../private.txt",
            "Content-Type": "application/octet-stream",
        },
    )
    assert response.status_code == 201, response.text
    fid = response.json()["id"]
    assert response.json()["filename"] == "private.txt"
    with application.state.sessions() as db:
        stored = db.get(StoredFile, fid)
        assert "Private attachment text" not in stored.encrypted_data
    downloaded = owner.get(f"/files/{fid}")
    assert downloaded.content == payload
    assert downloaded.headers["content-type"] == "application/octet-stream"
    assert downloaded.headers["content-disposition"].startswith("attachment;")
    assert other.get(f"/files/{fid}").status_code == 404
    assert other.delete(f"/files/{fid}").status_code == 404
    assert other.get(f"/tickets/{tid}/attachments").status_code == 404
    assert owner.delete(f"/files/{fid}").status_code == 204
    assert owner.get(f"/files/{fid}").status_code == 404


def test_document_ingestion_and_parent_deletion(application, monkeypatch):
    monkeypatch.setenv("FILE_ENCRYPTION_KEY", Fernet.generate_key().decode())
    owner = account(application)
    response = owner.post(
        "/knowledge/documents",
        content=b"# Refund policy\nRefunds require an agent review.",
        headers={"X-Filename": "refunds.md"},
    )
    assert response.status_code == 201, response.text
    aid = response.json()["article_id"]
    article = owner.get("/knowledge").json()[0]
    assert article["id"] == aid and "Refunds require" in article["content"]
    assert owner.delete(f"/knowledge/{aid}").status_code == 204
    assert owner.get(f"/files/{response.json()['file']['id']}").status_code == 404


@pytest.mark.parametrize(
    "filename,data",
    [
        ("attack.html", b"<script>bad()</script>"),
        ("fake.pdf", b"Not a PDF"),
        ("fake.png", b"Not a PNG"),
        ("empty.txt", b""),
    ],
)
def test_unsafe_uploads_rejected(application, monkeypatch, filename, data):
    monkeypatch.setenv("FILE_ENCRYPTION_KEY", Fernet.generate_key().decode())
    owner = account(application)
    assert (
        owner.post(
            f"/tickets/{ticket(owner)}/attachments",
            content=data,
            headers={"X-Filename": filename},
        ).status_code
        == 422
    )


def test_pdf_parser_rejects_image_only_or_unreadable_documents(
    application, monkeypatch
):
    monkeypatch.setenv("FILE_ENCRYPTION_KEY", Fernet.generate_key().decode())
    owner = account(application)
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    stream = io.BytesIO()
    writer.write(stream)
    result = owner.post(
        "/knowledge/documents",
        content=stream.getvalue(),
        headers={"X-Filename": "blank.pdf"},
    )
    assert result.status_code == 422
    with application.state.sessions() as db:
        assert db.scalar(select(StoredFile.id)) is None
