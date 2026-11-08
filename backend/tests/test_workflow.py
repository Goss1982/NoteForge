import io
import os
import zipfile
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import Session
from app.jobs import claim, enqueue, finish, heartbeat
from app.main import app
from app.models import Job, Notebook, Page, Revision, now
from app.providers import validate_document
from app.rendering import UnsupportedFormat, render_pages, validate_upload
from app.schemas import DocumentContent
from app.services import ingest, process_revision


def test_auth_csrf_and_private_files():
    with TestClient(app) as client:
        for route in [
            "/api/notebooks",
            "/api/status",
            "/api/documents",
            "/api/jobs",
            "/api/search?q=budget",
            "/api/insights",
            "/api/audit",
            "/api/pages/missing/image",
            "/api/revisions/missing/original",
        ]:
            assert client.get(route).status_code == 401
        assert client.post("/api/auth/login", json={"password": "wrong"}).status_code == 401
        assert (
            client.post(
                "/api/auth/login",
                json={"password": os.environ["ADMIN_PASSWORD"]},
                headers={"origin": "https://evil.example"},
            ).status_code
            == 403
        )
        assert (
            client.post("/api/auth/login", json={"password": os.environ["ADMIN_PASSWORD"]}).status_code == 200
        )
        cookie = client.cookies.get("nf_session")
        assert cookie
        assert client.post("/api/sync", headers={"sec-fetch-site": "cross-site"}).status_code == 403
        assert client.post("/api/auth/logout").status_code == 200
        assert client.get("/api/notebooks").status_code == 401
        client.cookies.set("nf_session", cookie + "tampered")
        assert client.get("/api/notebooks").status_code == 401


def test_login_rate_limit():
    with TestClient(app) as client:
        for _ in range(10):
            assert client.post("/api/auth/login", json={"password": "wrong"}).status_code == 401
        assert client.post("/api/auth/login", json={"password": "wrong"}).status_code == 429


def test_upload_preserves_bytes_and_queues(client, imported, pdf_bytes):
    response = client.get(f"/api/revisions/{imported['revision_id']}/original")
    assert response.content == pdf_bytes
    jobs = client.get("/api/jobs").json()
    assert len(jobs) == 1 and jobs[0]["kind"] == "process"
    assert client.get("/api/notebooks").json()[0]["status"] == "queued"
    assert client.get("/api/notebooks/missing").status_code == 404
    assert client.post(f"/api/revisions/{imported['revision_id']}/generate", json={}).status_code == 409
    assert client.post("/api/sync").status_code == 409


def test_unsupported_and_malformed_imports(client):
    for filename, data in [("file.exe", b"bad"), ("file.pdf", b"bad"), ("file.png", b"bad")]:
        assert client.post("/api/notebooks/import", files={"file": (filename, data)}).status_code == 422
    assert client.get("/api/notebooks").json() == []


def test_end_to_end_extraction_generation_review_and_export(client, ready, provider):
    detail = client.get(f"/api/notebooks/{ready['notebook_id']}").json()
    assert detail["revision"]["status"] == "ready"
    assert detail["category"] == "Meeting"
    page = detail["pages"][0]
    assert page["extraction"]["insights"][0]["owner"] == "Alex"
    assert client.get(f"/api/pages/{page['id']}/image").headers["content-type"] == "image/png"
    assert (
        client.patch(
            f"/api/pages/{page['id']}/review", json={"status": "verified", "note": "Checked handwriting"}
        ).status_code
        == 200
    )
    assert client.get("/api/insights").json()[0]["due_date"] == "Friday"
    matches = client.get("/api/search?q=proposal").json()
    assert len(matches) == 1 and matches[0]["page_id"] == page["id"]
    doc = client.get(f"/api/documents/{ready['document_id']}").json()
    assert doc["version"] == 1 and not doc["reviewed"]
    assert len(doc["versions"]) == 1
    content = doc["content"]
    content["sections"][0]["paragraphs"][0]["text"] = (
        "Alex will send the proposal on Friday, according to the notes."
    )
    saved = client.patch(
        f"/api/documents/{doc['id']}", json={"expected_version": 1, "content": content, "reviewed": True}
    )
    assert saved.status_code == 200 and saved.json()["version"] == 2
    # An old tab must never silently overwrite a newer version.
    assert (
        client.patch(
            f"/api/documents/{doc['id']}", json={"expected_version": 1, "content": content}
        ).status_code
        == 409
    )
    current = client.get(f"/api/documents/{doc['id']}").json()
    assert current["reviewed"] and len(current["versions"]) == 2
    assert current["versions"][1]["content"] != content
    exported = client.get(f"/api/documents/{doc['id']}/export").text
    assert "Source page 1" in exported and "Reviewed by user" in exported
    assert "Meeting date not specified" in exported
    assert client.get(f"/api/documents/{doc['id']}/export?format=json").json()["version"] == 2
    assert provider.calls == 1
    assert any(a["action"] == "document.edited" for a in client.get("/api/audit").json())


def test_rejects_foreign_or_invented_document_citations(client, ready):
    doc = client.get(f"/api/documents/{ready['document_id']}").json()
    content = doc["content"]
    for citation in [
        {"page_id": "foreign-page", "quote": "Budget"},
        {
            "page_id": content["sections"][0]["paragraphs"][0]["citations"][0]["page_id"],
            "quote": "Invented quote",
        },
    ]:
        content["sections"][0]["paragraphs"][0]["citations"] = [citation]
        assert (
            client.patch(
                f"/api/documents/{doc['id']}", json={"expected_version": 1, "content": content}
            ).status_code
            == 422
        )
    content["sections"][0]["paragraphs"][0]["citations"] = []
    assert (
        client.patch(
            f"/api/documents/{doc['id']}", json={"expected_version": 1, "content": content}
        ).status_code
        == 422
    )


def test_latest_revision_search_and_old_document_source(client, ready, pdf_bytes):
    with Session.begin() as db:
        notebook = db.get(Notebook, ready["notebook_id"])
        _, new = ingest(db, pdf_bytes + b"\n%new revision", "Meeting.pdf", notebook)
        new_id = new.id
    assert new_id != ready["revision_id"]
    assert client.get("/api/documents").json()[0]["stale"]
    assert client.get("/api/search?q=proposal").json() == []
    old = client.get(f"/api/notebooks/{ready['notebook_id']}?revision_id={ready['revision_id']}").json()
    assert old["pages"][0]["extraction"]["transcript"]
    assert len(old["revisions"]) == 2


def test_page_revision_must_belong_to_notebook(client, imported, pdf_bytes):
    other = client.post("/api/notebooks/import", files={"file": ("Other.pdf", pdf_bytes)}).json()
    assert (
        client.get(f"/api/notebooks/{imported['notebook_id']}?revision_id={other['revision_id']}").status_code
        == 404
    )


def test_ingest_revision_dedup_and_queue_dedup(client, imported, pdf_bytes):
    with Session.begin() as db:
        notebook = db.get(Notebook, imported["notebook_id"])
        _, revision = ingest(db, pdf_bytes, "Meeting.pdf", notebook)
        assert revision.id == imported["revision_id"]
        assert db.scalar(select(func.count()).select_from(Revision)) == 1
        assert db.scalar(select(func.count()).select_from(Job)) == 1


def test_resume_skips_finished_pages(client, ready, provider):
    with Session.begin() as db:
        job = enqueue(db, "process", {"revision_id": ready["revision_id"]}, "resume-test")
        job_id = job.id
    process_revision(job_id, ready["revision_id"])
    assert provider.calls == 1
    with Session() as db:
        assert db.scalar(select(func.count()).select_from(Page)) == 1


def test_bounded_retries_expired_leases_and_fencing(client, imported):
    job_id, token = claim()
    assert heartbeat(job_id, token)
    assert not heartbeat(job_id, "wrong")
    assert claim() is None
    finish(job_id, "wrong", "must not apply")
    with Session() as db:
        assert db.get(Job, job_id).status == "running"
    for attempt in range(1, 4):
        finish(job_id, token, "Transient provider failure")
        with Session.begin() as db:
            job = db.get(Job, job_id)
            assert job.attempts == attempt
            if attempt < 3:
                assert job.status == "queued"
                job.available_at = now() - timedelta(seconds=1)
            else:
                assert job.status == "failed" and job.active_key is None
        if attempt < 3:
            job_id, token = claim()
    result = client.post(f"/api/jobs/{job_id}/retry")
    assert result.status_code == 202
    new_id, new_token = claim()
    with Session.begin() as db:
        db.get(Job, new_id).lease_until = now() - timedelta(seconds=1)
    claimed_again = claim()
    assert claimed_again[0] == new_id and claimed_again[1] != new_token
    assert client.post(f"/api/jobs/{new_id}/retry").status_code == 409


def test_literal_search_does_not_treat_percent_as_wildcard(client, ready):
    assert client.get("/api/search?q=%25%25").json() == []
    assert client.get("/api/search?q=x").status_code == 422


def test_path_traversal_and_zip_bomb_are_rejected():
    for name in ["../escape", "/absolute", "bad\\path"]:
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as z:
            z.writestr(name, "bad")
        with pytest.raises(ValueError, match="Unsafe"):
            validate_upload(stream.getvalue(), ".rmdoc")
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("bomb", b"0" * 2_000_000)
    with pytest.raises(ValueError, match="compression ratio"):
        validate_upload(stream.getvalue(), ".rmdoc")


def test_rejects_ambiguous_notebook_rendering(tmp_path):
    source = tmp_path / "unsupported.rmdoc"
    with zipfile.ZipFile(source, "w") as z:
        z.writestr("doc.content", '{"pages":[]}')
    with pytest.raises(UnsupportedFormat, match="ordering"):
        render_pages(source, "unsupported-test")


def test_actual_pdf_and_image_rendering(pdf_bytes, tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(pdf_bytes)
    images, warning = render_pages(source, "render-test")
    assert len(images) == 1 and images[0].read_bytes().startswith(b"\x89PNG")
    assert warning is None
    validate_upload(images[0].read_bytes(), ".png")
    image_pages, _ = render_pages(images[0], "image-test")
    assert len(image_pages) == 1


def test_actual_v6_stroke_renderer(tmp_path):
    import json
    import subprocess

    markdown = tmp_path / "page.md"
    markdown.write_text("Test notebook content")
    stroke = tmp_path / "page.rm"
    subprocess.run(
        [
            str(Path(__import__("sys").executable).with_name("rmc")),
            "-t",
            "rm",
            str(markdown),
            "-o",
            str(stroke),
        ],
        check=True,
        capture_output=True,
    )
    archive = tmp_path / "notebook.rmdoc"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("notebook.content", json.dumps({"pages": ["page"]}))
        z.write(stroke, "notebook/page.rm")
    images, warning = render_pages(archive, "v6-test")
    assert len(images) == 1 and warning
    assert images[0].stat().st_size > 1000


def test_no_fabricated_citations_or_empty_fact():
    content = DocumentContent.model_validate(
        {
            "title": "Report",
            "sections": [
                {
                    "heading": "Summary",
                    "paragraphs": [{"kind": "fact", "text": "Unsupported assertion", "citations": []}],
                }
            ],
            "missing_information": [],
        }
    )
    with pytest.raises(ValueError, match="require source"):
        validate_document(content, {})


def test_upload_body_limits_before_multipart_spooling(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings(), "max_upload_mb", 1)
    assert (
        client.post(
            "/api/notebooks/import", content=b"x", headers={"content-length": str(3 * 1024 * 1024)}
        ).status_code
        == 413
    )
    response = client.post(
        "/api/notebooks/import",
        content=iter([b"x" * 1024 * 1024] * 3),
        headers={"content-type": "multipart/form-data; boundary=test"},
    )
    assert response.status_code == 413


def test_expired_final_lease_does_not_restart_forever(client, imported):
    job_id, token = claim()
    with Session.begin() as db:
        job = db.get(Job, job_id)
        job.attempts = 3
        job.lease_until = now() - timedelta(seconds=1)
    assert claim() is None
    with Session() as db:
        job = db.get(Job, job_id)
        assert job.status == "failed" and job.active_key is None
        assert db.get(Revision, imported["revision_id"]).status == "failed"


def test_completed_generation_is_idempotent(client, ready, provider):
    from app.models import Document, DocumentVersion
    from app.services import generate_document

    generate_document(ready["document_id"], ready["revision_id"], "meeting_minutes")
    with Session() as db:
        assert db.scalar(select(func.count()).select_from(Document)) == 1
        assert db.scalar(select(func.count()).select_from(DocumentVersion)) == 1
        assert not db.scalar(select(Job).where(Job.status == "queued"))


def test_cpages_uses_crdt_order_and_pdf_redirection(tmp_path):
    import json

    import fitz

    from app.rendering import _archive_pdf

    with fitz.open() as pdf:
        pdf.new_page().insert_text((50, 60), "Base page zero")
        pdf.new_page().insert_text((50, 60), "Base page one")
        base = pdf.tobytes()
    source = tmp_path / "cpages.rmdoc"
    with zipfile.ZipFile(source, "w") as z:
        z.writestr(
            "doc.content",
            json.dumps(
                {
                    "cPages": {
                        "pages": [
                            {"id": "second", "idx": {"value": "bb"}, "redir": {"value": 0}},
                            {"id": "deleted", "idx": {"value": "cc"}, "deleted": {"value": 0}},
                            {"id": "first", "idx": {"value": "aa"}, "redir": {"value": 1}},
                        ]
                    }
                }
            ),
        )
        z.writestr("doc.pdf", base)
    output = tmp_path / "output.pdf"
    _archive_pdf(source, output)
    with fitz.open(output) as pdf:
        assert len(pdf) == 2
        assert "Base page one" in pdf[0].get_text()
        assert "Base page zero" in pdf[1].get_text()
