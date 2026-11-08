from datetime import timedelta
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session as DBSession

from .auth import credential_id, login_rate_limit, password_matches, require_auth, serializer
from .body_limit import UploadBodyLimit
from .config import settings
from .db import get_db
from .exports import markdown
from .jobs import enqueue
from .models import AuditLog, Document, DocumentVersion, Job, Notebook, Page, Revision, RuntimeState, now
from .providers import validate_document
from .schemas import DocumentContent, EditDocument, GenerateRequest, PageReview
from .services import ingest
from .storage import safe_path

app = FastAPI(title="NoteForge API", version="0.1.0", docs_url=None, redoc_url=None, openapi_url=None)

app.add_middleware(UploadBodyLimit)


@app.middleware("http")
async def security(request: Request, call_next):
    # Same-origin browser mutations only, including login. Non-browser clients may omit Origin.
    origin = request.headers.get("origin")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        expected = urlsplit(settings().public_url)
        if request.headers.get("sec-fetch-site") == "cross-site" or (
            origin and origin.rstrip("/") != f"{expected.scheme}://{expected.netloc}"
        ):
            return Response("Cross-origin request rejected", status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response


class Login(BaseModel):
    password: str = Field(min_length=1, max_length=1024)


@app.get("/health")
def health(db: DBSession = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok"}


@app.post("/api/auth/login")
def login(body: Login, request: Request, response: Response):
    login_rate_limit(request)
    if not password_matches(body.password):
        raise HTTPException(401, "Incorrect password")
    fingerprint = credential_id()
    response.set_cookie(
        "nf_session",
        serializer().dumps({"role": "admin", "credential": fingerprint}),
        httponly=True,
        secure=settings().cookie_secure,
        samesite="strict",
        max_age=settings().session_hours * 3600,
        path="/",
    )
    return {"ok": True}


@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie("nf_session", path="/")
    return {"ok": True}


@app.get("/api/auth/me", dependencies=[Depends(require_auth)])
def me():
    return {"role": "admin"}


def get_or_404(db, model, identifier):
    obj = db.get(model, identifier)
    if obj is None:
        raise HTTPException(404, "Item not found")
    return obj


@app.get("/api/status", dependencies=[Depends(require_auth)])
def status(db: DBSession = Depends(get_db)):
    state = db.get(RuntimeState, "worker")
    running = db.scalar(select(Job).where(Job.status == "running").order_by(Job.updated_at.desc()).limit(1))
    heartbeat_at = max(
        [s for s in [state.updated_at if state else None, running.updated_at if running else None] if s],
        default=None,
    )
    worker_ok = bool(
        heartbeat_at and heartbeat_at.replace(tzinfo=now().tzinfo) > now() - timedelta(seconds=90)
    )
    return {
        "remarkable_paired": settings().rmapi_config.is_file(),
        "ai_configured": bool(settings().openai_api_key),
        "model": settings().openai_model,
        "worker_online": worker_ok,
        "sync_interval_seconds": settings().sync_interval_seconds,
        "auto_document_type": settings().auto_document_type,
        "counts": {
            "notebooks": db.scalar(select(func.count()).select_from(Notebook)),
            "documents": db.scalar(select(func.count()).select_from(Document)),
            "review": db.scalar(
                select(func.count()).select_from(Document).where(Document.reviewed.is_(False))
            ),
            "active_jobs": db.scalar(
                select(func.count()).select_from(Job).where(Job.status.in_(["queued", "running"]))
            ),
        },
    }


@app.get("/api/notebooks", dependencies=[Depends(require_auth)])
def notebooks(
    q: str = Query(default="", max_length=200),
    category: str = "",
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: DBSession = Depends(get_db),
):
    stmt = select(Notebook)
    if q:
        stmt = stmt.where(Notebook.title.contains(q, autoescape=True))
    if category:
        stmt = stmt.where(Notebook.category == category)
    items = db.scalars(stmt.order_by(Notebook.updated_at.desc()).offset(offset).limit(limit)).all()
    result = []
    for n in items:
        revision = db.get(Revision, n.latest_revision_id) if n.latest_revision_id else None
        count = db.scalar(
            select(func.count()).select_from(Page).where(Page.revision_id == n.latest_revision_id)
        )
        result.append(
            {
                "id": n.id,
                "title": n.title,
                "source": n.source,
                "category": n.category,
                "status": revision.status if revision else "queued",
                "pages": count,
                "updated_at": n.updated_at,
            }
        )
    return result


@app.post("/api/notebooks/import", dependencies=[Depends(require_auth)], status_code=202)
async def upload(file: UploadFile = File(...), db: DBSession = Depends(get_db)):
    data = await file.read(settings().max_upload_mb * 1024 * 1024 + 1)
    await file.close()
    if len(data) > settings().max_upload_mb * 1024 * 1024:
        raise HTTPException(413, "File exceeds configured upload limit")
    name = (file.filename or "notebook").replace("\\", "/").split("/")[-1]
    try:
        n, r = ingest(db, data, name)
        db.commit()
    except Exception as exc:
        db.rollback()
        if isinstance(exc, (ValueError, RuntimeError)):
            raise HTTPException(422, str(exc))
        raise HTTPException(422, "Unable to read this file; check its format and contents")
    return {"notebook_id": n.id, "revision_id": r.id}


@app.get("/api/notebooks/{notebook_id}", dependencies=[Depends(require_auth)])
def notebook_detail(notebook_id: str, revision_id: str | None = None, db: DBSession = Depends(get_db)):
    n = get_or_404(db, Notebook, notebook_id)
    revision = get_or_404(db, Revision, revision_id or n.latest_revision_id)
    if revision.notebook_id != n.id:
        raise HTTPException(404, "Revision not found in notebook")
    pages = db.scalars(select(Page).where(Page.revision_id == revision.id).order_by(Page.number)).all()
    versions = db.scalars(
        select(Revision).where(Revision.notebook_id == n.id).order_by(Revision.created_at.desc())
    ).all()
    return {
        "id": n.id,
        "title": n.title,
        "source": n.source,
        "category": n.category,
        "latest_revision_id": n.latest_revision_id,
        "revision": {
            "id": revision.id,
            "status": revision.status,
            "warning": revision.warning,
            "sha256": revision.sha256,
            "filename": revision.filename,
        },
        "revisions": [{"id": r.id, "created_at": r.created_at, "status": r.status} for r in versions],
        "pages": [
            {
                "id": p.id,
                "number": p.number,
                "extraction": p.extraction,
                "review_status": p.review_status,
                "review_note": p.review_note,
                "model": p.model,
            }
            for p in pages
        ],
    }


@app.get("/api/revisions/{revision_id}/original", dependencies=[Depends(require_auth)])
def original(revision_id: str, db: DBSession = Depends(get_db)):
    revision = get_or_404(db, Revision, revision_id)
    return FileResponse(
        safe_path(revision.original_path), filename=revision.filename, media_type="application/octet-stream"
    )


@app.get("/api/pages/{page_id}/image", dependencies=[Depends(require_auth)])
def page_image(page_id: str, db: DBSession = Depends(get_db)):
    page = get_or_404(db, Page, page_id)
    return FileResponse(safe_path(page.image_path), media_type="image/png")


@app.patch("/api/pages/{page_id}/review", dependencies=[Depends(require_auth)])
def review_page(page_id: str, body: PageReview, db: DBSession = Depends(get_db)):
    page = get_or_404(db, Page, page_id)
    page.review_status, page.review_note = body.status, body.note
    db.add(AuditLog(action="page.reviewed", target=page_id, detail=body.model_dump()))
    db.commit()
    return {"ok": True}


@app.post("/api/revisions/{revision_id}/generate", dependencies=[Depends(require_auth)], status_code=202)
def generate(revision_id: str, body: GenerateRequest, db: DBSession = Depends(get_db)):
    revision = get_or_404(db, Revision, revision_id)
    if revision.status != "ready":
        raise HTTPException(409, "Wait until handwriting extraction is complete")
    job = enqueue(
        db, "generate", {"revision_id": revision_id, "kind": body.kind}, f"generate:{revision_id}:{body.kind}"
    )
    db.commit()
    return {"job_id": job.id}


@app.post("/api/sync", dependencies=[Depends(require_auth)], status_code=202)
def sync(db: DBSession = Depends(get_db)):
    if not settings().rmapi_config.is_file():
        raise HTTPException(409, "Pair reMarkable on the server first. See Settings for instructions.")
    job = enqueue(db, "sync", {}, "sync")
    db.commit()
    return {"job_id": job.id}


@app.get("/api/jobs", dependencies=[Depends(require_auth)])
def jobs(db: DBSession = Depends(get_db)):
    return [
        {
            "id": j.id,
            "kind": j.kind,
            "status": j.status,
            "attempts": j.attempts,
            "progress": j.progress,
            "error": j.error,
            "created_at": j.created_at,
            "updated_at": j.updated_at,
        }
        for j in db.scalars(select(Job).order_by(Job.created_at.desc()).limit(100)).all()
    ]


@app.post("/api/jobs/{job_id}/retry", dependencies=[Depends(require_auth)], status_code=202)
def retry(job_id: str, db: DBSession = Depends(get_db)):
    job = get_or_404(db, Job, job_id)
    if job.status != "failed":
        raise HTTPException(409, "Only failed jobs can be retried")
    if job.kind == "sync":
        key = "sync"
    elif job.kind == "process":
        key = f"process:{job.payload['revision_id']}"
    else:
        key = f"generate:{job.payload['revision_id']}:{job.payload['kind']}"
    result = enqueue(db, job.kind, job.payload, key)
    db.commit()
    return {"job_id": result.id}


@app.get("/api/documents", dependencies=[Depends(require_auth)])
def documents(db: DBSession = Depends(get_db)):
    rows = db.execute(
        select(Document, Notebook)
        .join(Notebook, Notebook.id == Document.notebook_id)
        .order_by(Document.created_at.desc())
        .limit(100)
    ).all()
    return [
        {
            "id": d.id,
            "title": d.title,
            "kind": d.kind,
            "reviewed": d.reviewed,
            "version": d.version,
            "created_at": d.created_at,
            "notebook_title": n.title,
            "notebook_id": n.id,
            "stale": d.revision_id != n.latest_revision_id,
        }
        for d, n in rows
    ]


@app.get("/api/documents/{document_id}", dependencies=[Depends(require_auth)])
def document(document_id: str, db: DBSession = Depends(get_db)):
    d = get_or_404(db, Document, document_id)
    n = get_or_404(db, Notebook, d.notebook_id)
    versions = db.scalars(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == d.id)
        .order_by(DocumentVersion.number.desc())
    ).all()
    return {
        "id": d.id,
        "notebook_id": d.notebook_id,
        "revision_id": d.revision_id,
        "content": d.content,
        "kind": d.kind,
        "reviewed": d.reviewed,
        "version": d.version,
        "model": d.model,
        "stale": d.revision_id != n.latest_revision_id,
        "versions": [
            {"number": v.number, "created_at": v.created_at, "reviewed": v.reviewed, "content": v.content}
            for v in versions
        ],
    }


@app.patch("/api/documents/{document_id}", dependencies=[Depends(require_auth)])
def edit_document(document_id: str, body: EditDocument, db: DBSession = Depends(get_db)):
    d = get_or_404(db, Document, document_id)
    pages = db.scalars(select(Page).where(Page.revision_id == d.revision_id)).all()
    try:
        validate_document(body.content, {p.id: p.search_text for p in pages})
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    result = db.execute(
        update(Document)
        .where(Document.id == document_id, Document.version == body.expected_version)
        .values(
            content=body.content.model_dump(),
            title=body.content.title,
            reviewed=body.reviewed,
            version=body.expected_version + 1,
        )
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Document changed. Reload it before saving.")
    db.add(
        DocumentVersion(
            document_id=document_id,
            number=body.expected_version + 1,
            content=body.content.model_dump(),
            reviewed=body.reviewed,
        )
    )
    db.add(
        AuditLog(
            action="document.edited",
            target=document_id,
            detail={"version": body.expected_version + 1, "reviewed": body.reviewed},
        )
    )
    db.commit()
    return {"version": body.expected_version + 1}


@app.get("/api/documents/{document_id}/export", dependencies=[Depends(require_auth)])
def export(
    document_id: str,
    format: str = Query("markdown", pattern="^(markdown|json)$"),
    db: DBSession = Depends(get_db),
):
    d = get_or_404(db, Document, document_id)
    if format == "json":
        import json

        return Response(
            json.dumps(
                {
                    "content": d.content,
                    "reviewed": d.reviewed,
                    "revision_id": d.revision_id,
                    "version": d.version,
                },
                ensure_ascii=False,
                indent=2,
            ),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="noteforge-{d.id}.json"'},
        )
    pages = db.scalars(select(Page).where(Page.revision_id == d.revision_id)).all()
    text = markdown(
        DocumentContent.model_validate(d.content),
        {p.id: p.number for p in pages},
        reviewed=d.reviewed,
        revision_id=d.revision_id,
    )
    return PlainTextResponse(
        text, headers={"Content-Disposition": f'attachment; filename="noteforge-{d.id}.md"'}
    )


@app.get("/api/search", dependencies=[Depends(require_auth)])
def search(q: str = Query(min_length=2, max_length=200), db: DBSession = Depends(get_db)):
    rows = db.execute(
        select(Page, Revision, Notebook)
        .join(Revision, Revision.id == Page.revision_id)
        .join(Notebook, Notebook.id == Revision.notebook_id)
        .where(Page.search_text.contains(q, autoescape=True), Notebook.latest_revision_id == Revision.id)
        .order_by(Notebook.updated_at.desc(), Page.number)
        .limit(50)
    ).all()
    results = []
    for page, revision, notebook in rows:
        at = page.search_text.lower().find(q.lower())
        results.append(
            {
                "page_id": page.id,
                "notebook_id": notebook.id,
                "notebook_title": notebook.title,
                "revision_id": revision.id,
                "number": page.number,
                "excerpt": page.search_text[max(0, at - 100) : max(0, at) + 300],
            }
        )
    return results


@app.get("/api/insights", dependencies=[Depends(require_auth)])
def insights(db: DBSession = Depends(get_db)):
    rows = db.execute(
        select(Page, Notebook)
        .join(Revision, Revision.id == Page.revision_id)
        .join(Notebook, Notebook.latest_revision_id == Revision.id)
        .where(Page.extraction.is_not(None))
        .order_by(Notebook.updated_at.desc())
        .limit(500)
    ).all()
    return [
        {
            **item,
            "page_id": p.id,
            "number": p.number,
            "notebook_id": n.id,
            "notebook_title": n.title,
            "review_status": p.review_status,
        }
        for p, n in rows
        for item in (p.extraction or {}).get("insights", [])
    ]


@app.get("/api/audit", dependencies=[Depends(require_auth)])
def audit(db: DBSession = Depends(get_db)):
    return [
        {"id": a.id, "action": a.action, "target": a.target, "detail": a.detail, "created_at": a.created_at}
        for a in db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(100)).all()
    ]
